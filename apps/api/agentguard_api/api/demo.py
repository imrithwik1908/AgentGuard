from datetime import timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from agentguard_api.core.config import Settings, get_settings
from agentguard_api.core.time import utc_now
from agentguard_api.db.session import get_session
from agentguard_api.models import ApplicationVersion, Project
from agentguard_api.models.enums import RunStatus, SpanType
from agentguard_api.schemas.dataset import DatasetCreate
from agentguard_api.schemas.trace import SpanIngest, TraceIngest
from agentguard_api.services.datasets import create_dataset, run_dataset_case
from agentguard_api.services.errors import NotFoundError
from agentguard_api.services.evaluations import (
    create_status_evaluation,
    create_trace_health_evaluations,
)
from agentguard_api.services.security import AuthContext, get_auth_context
from agentguard_api.services.trace_ingestion import ingest_trace

router = APIRouter(prefix="/demo", tags=["demo"])


class DemoSeedResult(BaseModel):
    project_id: str
    baseline_version_id: str
    candidate_version_id: str
    dataset_id: str
    trace_ids: list[str]
    message: str


@router.post("/seed", response_model=DemoSeedResult, status_code=201)
async def seed_demo(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    auth: AuthContext = Depends(get_auth_context),
) -> DemoSeedResult:
    if not settings.demo_seed_enabled:
        raise NotFoundError("demo seed endpoint is disabled")

    project = await _ensure_project(session, auth.workspace_id)
    baseline = await _ensure_version(session, project, "v1", "Stable baseline")
    candidate = await _ensure_version(session, project, "v2", "Regression candidate")
    project_id = project.id
    project_slug = project.slug
    baseline_id = baseline.id
    baseline_version = baseline.version
    candidate_id = candidate.id
    candidate_version = candidate.version

    success_trace = await _ensure_trace(
        session,
        settings,
        project_slug,
        baseline_version,
        "demo-success-v1-nested",
        RunStatus.OK,
        "AgentGuard captures traces for LLM, RAG, and agentic applications.",
        workspace_id=auth.workspace_id,
    )
    failed_trace = await _ensure_trace(
        session,
        settings,
        project_slug,
        candidate_version,
        "demo-failure-v2-nested",
        RunStatus.ERROR,
        None,
        workspace_id=auth.workspace_id,
    )
    success_trace_id = success_trace.id
    failed_trace_id = failed_trace.id
    await _ensure_status_eval(session, success_trace_id, workspace_id=auth.workspace_id)
    await _ensure_status_eval(session, failed_trace_id, workspace_id=auth.workspace_id)
    await _ensure_health_eval(session, success_trace_id, workspace_id=auth.workspace_id)
    await _ensure_health_eval(session, failed_trace_id, workspace_id=auth.workspace_id)

    dataset = await _ensure_dataset(session, project_id, workspace_id=auth.workspace_id)
    dataset_id = dataset.id
    first_case_id = dataset.cases[0].id if dataset.cases else None
    if first_case_id is not None:
        await run_dataset_case(
            session,
            case_id=first_case_id,
            application_version_id=baseline_id,
            evaluator_name="builtin.answer_contains",
            settings=settings,
            workspace_id=auth.workspace_id,
        )

    return DemoSeedResult(
        project_id=str(project_id),
        baseline_version_id=str(baseline_id),
        candidate_version_id=str(candidate_id),
        dataset_id=str(dataset_id),
        trace_ids=[str(success_trace_id), str(failed_trace_id)],
        message="Demo project, versions, traces, dataset, and evaluations are ready.",
    )


async def _ensure_project(session: AsyncSession, workspace_id) -> Project:
    slug = "agentguard-demo"
    if workspace_id is not None:
        slug = f"agentguard-demo-{str(workspace_id)[:8]}"

    project = await session.scalar(
        select(Project).where(
            Project.slug == slug,
            Project.workspace_id == workspace_id,
        )
    )
    if project:
        return project
    project = Project(
        name="AgentGuard Demo",
        slug=slug,
        description="Seeded public demo data for exploring AgentGuard.",
        workspace_id=workspace_id,
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def _ensure_version(
    session: AsyncSession,
    project: Project,
    version_name: str,
    name: str,
) -> ApplicationVersion:
    version = await session.scalar(
        select(ApplicationVersion).where(
            ApplicationVersion.project_id == project.id,
            ApplicationVersion.version == version_name,
        )
    )
    if version:
        return version
    version = ApplicationVersion(project_id=project.id, name=name, version=version_name)
    session.add(version)
    await session.commit()
    await session.refresh(version)
    return version


async def _ensure_trace(
    session: AsyncSession,
    settings: Settings,
    project_slug: str,
    version: str,
    external_trace_id: str,
    status: RunStatus,
    answer: str | None,
    *,
    workspace_id,
):
    from agentguard_api.models import Trace

    existing = await session.scalar(
        select(Trace)
        .join(Project)
        .where(
            Trace.external_trace_id == external_trace_id,
            Trace.project_id == Project.id,
            Project.workspace_id == workspace_id,
        )
    )
    if existing:
        return existing

    started = utc_now()
    error = (
        {"type": "RuntimeError", "message": "candidate generation failed", "code": None}
        if status == RunStatus.ERROR
        else None
    )
    route_ended = started + timedelta(milliseconds=12)
    retrieve_ended = started + timedelta(milliseconds=64)
    generate_ended = started + timedelta(milliseconds=145)
    trace = await ingest_trace(
        session,
        TraceIngest(
            project_slug=project_slug,
            version=version,
            external_trace_id=external_trace_id,
            name="answer-question",
            status=status,
            input={"question": "What is AgentGuard?"},
            output={"answer": answer} if answer else None,
            metadata={"source": "public_demo"},
            started_at=started,
            ended_at=generate_ended,
            error=error,
            spans=[
                SpanIngest(
                    external_span_id="route-question",
                    type=SpanType.CHAIN,
                    name="route-question",
                    status=RunStatus.OK,
                    input={"question": "What is AgentGuard?"},
                    output={"route": "answer-with-local-corpus"},
                    provider="local",
                    model_name="demo-router",
                    started_at=started,
                    ended_at=route_ended,
                ),
                SpanIngest(
                    external_span_id="retrieve-context",
                    parent_external_span_id="route-question",
                    type=SpanType.RETRIEVER,
                    name="retrieve-context",
                    status=RunStatus.OK,
                    input={"query": "What is AgentGuard?"},
                    output={
                        "documents": [
                            {
                                "id": "doc-agentguard",
                                "title": "AgentGuard",
                                "score": 0.96,
                            }
                        ]
                    },
                    provider="local",
                    model_name=None,
                    started_at=started,
                    ended_at=retrieve_ended,
                ),
                SpanIngest(
                    external_span_id="generate",
                    parent_external_span_id="route-question",
                    type=SpanType.LLM,
                    name="generate",
                    status=status,
                    input={
                        "question": "What is AgentGuard?",
                        "context_ids": ["doc-agentguard"],
                    },
                    output={"answer": answer} if answer else None,
                    provider="local",
                    model_name="demo-model",
                    started_at=started,
                    ended_at=generate_ended,
                    error=error,
                )
            ],
        ),
        settings,
        workspace_id=workspace_id,
    )
    return trace


async def _ensure_status_eval(session: AsyncSession, trace_id, *, workspace_id) -> None:
    try:
        await create_status_evaluation(session, trace_id, workspace_id=workspace_id)
    except Exception:
        await session.rollback()


async def _ensure_health_eval(session: AsyncSession, trace_id, *, workspace_id) -> None:
    try:
        await create_trace_health_evaluations(session, trace_id, workspace_id=workspace_id)
    except Exception:
        await session.rollback()


async def _ensure_dataset(session: AsyncSession, project_id, *, workspace_id):
    from agentguard_api.models import Dataset

    existing = await session.scalar(
        select(Dataset)
        .options(selectinload(Dataset.cases))
        .where(Dataset.project_id == project_id, Dataset.slug == "demo-golden-set")
    )
    if existing:
        return existing
    return await create_dataset(
        session,
        DatasetCreate(
            project_id=project_id,
            name="Demo Golden Set",
            slug="demo-golden-set",
            description="Expected behavior examples for judging the demo agent.",
            cases=[
                {
                    "name": "explains-agentguard",
                    "input": {"question": "What is AgentGuard?"},
                    "expected_substring": "captures traces",
                }
            ],
        ),
        workspace_id=workspace_id,
    )
