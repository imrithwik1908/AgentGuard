import uuid
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from agentguard_api.core.config import Settings
from agentguard_api.core.time import utc_now
from agentguard_api.db.session import AsyncSessionLocal
from agentguard_api.models import (
    ApplicationVersion,
    Dataset,
    EvaluationJob,
    EvaluationJobCase,
    EvaluationJobCaseStatus,
    EvaluationJobStatus,
    Project,
)
from agentguard_api.schemas.evaluation import EvaluationJobCreate
from agentguard_api.services.datasets import run_dataset_case
from agentguard_api.services.errors import NotFoundError, ValidationError


def _error_dict(exc: Exception) -> dict:
    return {"type": type(exc).__name__, "message": str(exc)}


async def enqueue_evaluation_job(
    session: AsyncSession,
    payload: EvaluationJobCreate,
    *,
    workspace_id: UUID | None = None,
) -> EvaluationJob:
    dataset_query = (
        select(Dataset)
        .options(selectinload(Dataset.cases))
        .join(Project)
        .where(Dataset.id == payload.dataset_id)
    )
    if workspace_id is not None:
        dataset_query = dataset_query.where(Project.workspace_id == workspace_id)
    dataset = await session.scalar(dataset_query)
    if dataset is None:
        raise NotFoundError("dataset was not found")

    version_query = (
        select(ApplicationVersion)
        .join(Project)
        .where(ApplicationVersion.id == payload.application_version_id)
    )
    if workspace_id is not None:
        version_query = version_query.where(Project.workspace_id == workspace_id)
    version = await session.scalar(version_query)
    if version is None:
        raise NotFoundError("application version was not found")
    if version.project_id != dataset.project_id:
        raise ValidationError("dataset and application version must belong to the same project")

    request_id = payload.request_id or str(uuid.uuid4())
    existing = await session.scalar(
        select(EvaluationJob)
        .options(selectinload(EvaluationJob.cases))
        .where(
            EvaluationJob.dataset_id == dataset.id,
            EvaluationJob.application_version_id == version.id,
            EvaluationJob.evaluator_name == payload.evaluator_name,
            EvaluationJob.request_id == request_id,
        )
    )
    if existing is not None:
        return existing

    job = EvaluationJob(
        request_id=request_id,
        project_id=dataset.project_id,
        dataset_id=dataset.id,
        application_version_id=version.id,
        evaluator_name=payload.evaluator_name,
        total_cases=len(dataset.cases),
        completed_cases=0,
        failed_cases=0,
        max_attempts=payload.max_attempts,
        status=EvaluationJobStatus.QUEUED,
    )
    session.add(job)
    await session.flush()
    for case in dataset.cases:
        session.add(EvaluationJobCase(job_id=job.id, dataset_case_id=case.id))
    await session.commit()
    return await get_evaluation_job(session, job.id, workspace_id=workspace_id)


async def get_evaluation_job(
    session: AsyncSession,
    job_id: UUID,
    *,
    workspace_id: UUID | None = None,
) -> EvaluationJob:
    stmt = (
        select(EvaluationJob)
        .options(selectinload(EvaluationJob.cases))
        .where(EvaluationJob.id == job_id)
    )
    if workspace_id is not None:
        stmt = stmt.join(Project, Project.id == EvaluationJob.project_id).where(
            Project.workspace_id == workspace_id
        )
    job = await session.scalar(stmt)
    if job is None:
        raise NotFoundError("evaluation job was not found")
    job.cases.sort(key=lambda case: case.created_at)
    return job


async def process_evaluation_job(
    job_id: UUID,
    *,
    settings: Settings,
    workspace_id: UUID | None = None,
) -> None:
    async with AsyncSessionLocal() as session:
        job = await get_evaluation_job(session, job_id, workspace_id=workspace_id)
        if job.status in {EvaluationJobStatus.COMPLETED, EvaluationJobStatus.PARTIAL}:
            return
        job.status = EvaluationJobStatus.RUNNING
        job.started_at = job.started_at or utc_now()
        await session.commit()

    async with AsyncSessionLocal() as session:
        job = await get_evaluation_job(session, job_id, workspace_id=workspace_id)
        for job_case in job.cases:
            if job_case.status == EvaluationJobCaseStatus.COMPLETED:
                continue
            while job_case.attempts < job.max_attempts:
                job_case.status = EvaluationJobCaseStatus.RUNNING
                job_case.started_at = job_case.started_at or utc_now()
                job_case.attempts += 1
                await session.commit()
                try:
                    trace, evaluation = await run_dataset_case(
                        session,
                        case_id=job_case.dataset_case_id,
                        application_version_id=job.application_version_id,
                        evaluator_name=job.evaluator_name,
                        settings=settings,
                        workspace_id=workspace_id,
                    )
                    job_case.trace_id = trace.id
                    job_case.evaluation_result_id = evaluation.id
                    job_case.status = EvaluationJobCaseStatus.COMPLETED
                    job_case.error = None
                    job_case.finished_at = utc_now()
                    await session.commit()
                    break
                except Exception as exc:
                    await session.rollback()
                    job_case = await session.get(EvaluationJobCase, job_case.id)
                    if job_case is None:
                        raise
                    job_case.error = _error_dict(exc)
                    if job_case.attempts >= job.max_attempts:
                        job_case.status = EvaluationJobCaseStatus.FAILED
                        job_case.finished_at = utc_now()
                    else:
                        job_case.status = EvaluationJobCaseStatus.QUEUED
                    await session.commit()

        refreshed = await get_evaluation_job(session, job_id, workspace_id=workspace_id)
        completed = sum(
            1 for case in refreshed.cases if case.status == EvaluationJobCaseStatus.COMPLETED
        )
        failed = sum(1 for case in refreshed.cases if case.status == EvaluationJobCaseStatus.FAILED)
        refreshed.completed_cases = completed
        refreshed.failed_cases = failed
        refreshed.finished_at = utc_now()
        if completed == refreshed.total_cases:
            refreshed.status = EvaluationJobStatus.COMPLETED
        elif completed > 0:
            refreshed.status = EvaluationJobStatus.PARTIAL
        else:
            refreshed.status = EvaluationJobStatus.FAILED
            refreshed.error = {"message": "all evaluation cases failed"}
        await session.commit()
