import uuid
from datetime import timedelta
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from agentguard_api.core.config import Settings
from agentguard_api.core.time import utc_now
from agentguard_api.db.session import AsyncSessionLocal
from agentguard_api.models import (
    ApplicationVersion,
    Dataset,
    DatasetCase,
    EvaluationJob,
    EvaluationJobCase,
    EvaluationJobCaseStatus,
    EvaluationJobStatus,
    Project,
    Trace,
)
from agentguard_api.schemas.evaluation import EvaluationJobCreate
from agentguard_api.services.errors import NotFoundError, ValidationError
from agentguard_api.services.evaluator_runner import (
    evaluate_trace_against_case,
    evaluator_applies_to_case,
)


def _error_dict(exc: Exception) -> dict:
    return {
        "type": type(exc).__name__,
        "message": str(exc),
    }


def redis_settings_from_url(redis_url: str):
    from arq.connections import RedisSettings

    parsed = urlparse(redis_url)
    ssl_enabled = parsed.scheme == "rediss"
    database = int(parsed.path.lstrip("/") or "0")
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=database,
        password=parsed.password,
        ssl=ssl_enabled,
    )


def stable_queue_job_id(job_id: UUID) -> str:
    return f"evaluation-job:{job_id}"


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

    applicable_cases = [
        case for case in dataset.cases if evaluator_applies_to_case(payload.evaluator_name, case)
    ]

    job = EvaluationJob(
        request_id=request_id,
        queue_job_id=None,
        project_id=dataset.project_id,
        dataset_id=dataset.id,
        application_version_id=version.id,
        evaluator_name=payload.evaluator_name,
        total_cases=len(applicable_cases),
        completed_cases=0,
        failed_cases=0,
        max_attempts=payload.max_attempts,
        status=EvaluationJobStatus.QUEUED,
    )

    session.add(job)
    await session.flush()

    for case in applicable_cases:
        session.add(
            EvaluationJobCase(
                job_id=job.id,
                dataset_case_id=case.id,
            )
        )

    await session.commit()

    return await get_evaluation_job(
        session,
        job.id,
        workspace_id=workspace_id,
    )


async def enqueue_evaluation_job_for_processing(
    session: AsyncSession,
    job: EvaluationJob,
    *,
    settings: Settings,
    workspace_id: UUID | None = None,
) -> EvaluationJob:
    if settings.evaluation_queue_backend != "redis":
        await process_evaluation_job(
            job.id,
            settings=settings,
            workspace_id=workspace_id,
        )
        return await get_evaluation_job(
            session,
            job.id,
            workspace_id=workspace_id,
        )

    from arq import create_pool

    queue_job_id = job.queue_job_id or stable_queue_job_id(job.id)
    redis = await create_pool(redis_settings_from_url(settings.redis_url))
    try:
        await redis.enqueue_job(
            "process_evaluation_job_arq",
            str(job.id),
            str(workspace_id) if workspace_id is not None else None,
            _job_id=queue_job_id,
        )
    finally:
        await redis.close()

    job.queue_job_id = queue_job_id
    await session.commit()
    return await get_evaluation_job(
        session,
        job.id,
        workspace_id=workspace_id,
    )


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
        stmt = stmt.join(
            Project,
            Project.id == EvaluationJob.project_id,
        ).where(Project.workspace_id == workspace_id)

    job = await session.scalar(stmt)

    if job is None:
        raise NotFoundError("evaluation job was not found")

    job.cases.sort(key=lambda case: case.created_at)

    return job


async def recover_stale_evaluation_jobs(
    session: AsyncSession,
    *,
    stale_after_seconds: int,
) -> None:
    cutoff = utc_now() - timedelta(seconds=stale_after_seconds)

    result = await session.execute(
        select(EvaluationJob.id).where(
            EvaluationJob.status == EvaluationJobStatus.RUNNING,
            EvaluationJob.started_at < cutoff,
        )
    )

    job_ids = list(result.scalars())

    if not job_ids:
        return

    await session.execute(
        update(EvaluationJob)
        .where(EvaluationJob.id.in_(job_ids))
        .values(
            status=EvaluationJobStatus.QUEUED,
            error={"message": ("Recovered after worker interruption")},
        )
    )

    await session.execute(
        update(EvaluationJobCase)
        .where(
            EvaluationJobCase.job_id.in_(job_ids),
            EvaluationJobCase.status == EvaluationJobCaseStatus.RUNNING,
        )
        .values(
            status=EvaluationJobCaseStatus.QUEUED,
        )
    )

    await session.commit()


async def claim_next_evaluation_job(
    session: AsyncSession,
) -> tuple[UUID, UUID | None] | None:
    async with session.begin():
        stmt = (
            select(EvaluationJob)
            .where(EvaluationJob.status == EvaluationJobStatus.QUEUED)
            .order_by(EvaluationJob.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
        )

        job = await session.scalar(stmt)

        if job is None:
            return None

        job.status = EvaluationJobStatus.RUNNING
        job.started_at = job.started_at or utc_now()

        workspace_id = await session.scalar(
            select(Project.workspace_id).where(Project.id == job.project_id)
        )

        job_id = job.id

    return job_id, workspace_id


async def _find_trace_for_case(
    session: AsyncSession,
    *,
    project_id: UUID,
    application_version_id: UUID,
    dataset_case_id: UUID,
    workspace_id: UUID | None,
) -> Trace | None:

    case_id = str(dataset_case_id)

    stmt = (
        select(Trace)
        .options(selectinload(Trace.spans))
        .join(Project, Project.id == Trace.project_id)
        .where(
            Trace.project_id == project_id,
            Trace.application_version_id == application_version_id,
            or_(
                Trace.meta["dataset_case_id"].astext == case_id,
                Trace.input["dataset_case_id"].astext == case_id,
            ),
        )
        .order_by(Trace.created_at.desc())
        .limit(1)
    )

    if workspace_id is not None:
        stmt = stmt.where(Project.workspace_id == workspace_id)

    return await session.scalar(stmt)


async def process_evaluation_job(
    job_id: UUID,
    *,
    settings: Settings,
    workspace_id: UUID | None = None,
) -> None:

    async with AsyncSessionLocal() as session:
        job = await get_evaluation_job(
            session,
            job_id,
            workspace_id=workspace_id,
        )

        if job.status in {
            EvaluationJobStatus.COMPLETED,
            EvaluationJobStatus.PARTIAL,
        }:
            return

        if job.status == EvaluationJobStatus.QUEUED:
            job.status = EvaluationJobStatus.RUNNING
            job.started_at = job.started_at or utc_now()
            await session.commit()

    async with AsyncSessionLocal() as session:
        job = await get_evaluation_job(
            session,
            job_id,
            workspace_id=workspace_id,
        )
        application_version_id = job.application_version_id
        evaluator_name = job.evaluator_name
        max_attempts = job.max_attempts
        project_id = job.project_id

        job_case_ids = [job_case.id for job_case in job.cases]
        for job_case_id in job_case_ids:
            job_case = await session.get(EvaluationJobCase, job_case_id)
            if job_case is None:
                continue
            if job_case.status == EvaluationJobCaseStatus.COMPLETED:
                continue

            while job_case.attempts < max_attempts:
                attempt_number = job_case.attempts + 1
                job_case.status = EvaluationJobCaseStatus.RUNNING
                job_case.started_at = job_case.started_at or utc_now()
                job_case.attempts = attempt_number

                await session.commit()

                try:
                    case = await session.get(
                        DatasetCase,
                        job_case.dataset_case_id,
                    )

                    if case is None:
                        raise ValidationError("dataset case no longer exists")

                    trace = await _find_trace_for_case(
                        session,
                        project_id=project_id,
                        application_version_id=(application_version_id),
                        dataset_case_id=case.id,
                        workspace_id=workspace_id,
                    )

                    if trace is None:
                        raise ValidationError(
                            (
                                "No captured application run "
                                "was found for this test case "
                                "and version. Run the test case "
                                "through the instrumented "
                                "application first."
                            ),
                            metadata={
                                "dataset_case_id": str(case.id),
                                "application_version_id": str(application_version_id),
                            },
                        )

                    evaluation = await evaluate_trace_against_case(
                        session,
                        trace=trace,
                        case=case,
                        evaluator_name=(evaluator_name),
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

                    failed_permanently = attempt_number >= max_attempts
                    await session.execute(
                        update(EvaluationJobCase)
                        .where(EvaluationJobCase.id == job_case_id)
                        .values(
                            error=_error_dict(exc),
                            status=(
                                EvaluationJobCaseStatus.FAILED
                                if failed_permanently
                                else EvaluationJobCaseStatus.QUEUED
                            ),
                            finished_at=(utc_now() if failed_permanently else None),
                        )
                    )

                    await session.commit()
                    if failed_permanently:
                        break
                    job_case = await session.get(
                        EvaluationJobCase,
                        job_case_id,
                    )
                    if job_case is None:
                        raise

        refreshed = await get_evaluation_job(
            session,
            job_id,
            workspace_id=workspace_id,
        )

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
            refreshed.error = {"message": ("No test cases could be evaluated")}

        await session.commit()
