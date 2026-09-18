from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from agentguard_api.core.config import Settings, get_settings
from agentguard_api.core.time import utc_now
from agentguard_api.db.session import get_session
from agentguard_api.models import ApplicationVersion, Project, Trace
from agentguard_api.models.enums import RunStatus, SpanType
from agentguard_api.schemas.dataset import DatasetCaseCreate, DatasetCreate
from agentguard_api.schemas.trace import SpanIngest, TraceIngest
from agentguard_api.services.datasets import create_dataset, create_dataset_case
from agentguard_api.services.evaluations import (
    create_status_evaluation,
    create_trace_health_evaluations,
)
from agentguard_api.services.evaluator_runner import evaluate_trace_against_case
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "demo_seed_disabled",
                "message": "Demo data loading is disabled for this deployment.",
            },
        )

    project = await _ensure_project(session, auth.workspace_id)
    baseline = await _ensure_version(
        session,
        project,
        "v1",
        "Stable baseline",
        retrieval_config={"top_k": 4, "strategy": "keyword"},
    )
    candidate = await _ensure_version(
        session,
        project,
        "v2",
        "Regression candidate",
        retrieval_config={"top_k": 10, "strategy": "keyword"},
    )
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
    behavior_trace_ids = await _ensure_paired_demo_evidence(
        session,
        settings=settings,
        dataset=dataset,
        project_slug=project_slug,
        baseline_version=baseline_version,
        candidate_version=candidate_version,
        workspace_id=auth.workspace_id,
    )

    return DemoSeedResult(
        project_id=str(project_id),
        baseline_version_id=str(baseline_id),
        candidate_version_id=str(candidate_id),
        dataset_id=str(dataset_id),
        trace_ids=[str(success_trace_id), str(failed_trace_id), *behavior_trace_ids],
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
    retrieval_config: dict,
) -> ApplicationVersion:
    version = await session.scalar(
        select(ApplicationVersion).where(
            ApplicationVersion.project_id == project.id,
            ApplicationVersion.version == version_name,
        )
    )
    if version:
        if version.retrieval_config != retrieval_config:
            version.retrieval_config = retrieval_config
            await session.commit()
            await session.refresh(version)
        return version
    version = ApplicationVersion(
        project_id=project.id,
        name=name,
        version=version_name,
        retrieval_config=retrieval_config,
    )
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
                ),
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
    case_payloads = [
        DatasetCaseCreate(
            name="explains-agentguard",
            input={"question": "What is AgentGuard?"},
            expected_substring="captures traces",
            evaluators=["builtin.answer_contains"],
        ),
        DatasetCaseCreate(
            name="supports-release-decisions",
            input={"question": "How does AgentGuard help before release?"},
            expected_substring="release decisions",
            expectations={
                "required_sources": ["release-policy"],
                "expected_tool": "policy_lookup",
            },
            evaluators=[
                "builtin.answer_contains",
                "builtin.required_source",
                "builtin.expected_tool",
            ],
        ),
        DatasetCaseCreate(
            name="records-execution-steps",
            input={"question": "What evidence does AgentGuard record?"},
            expected_substring="nested steps",
            expectations={
                "required_sources": ["instrumentation-guide"],
                "expected_tool": "policy_lookup",
            },
            evaluators=[
                "builtin.answer_contains",
                "builtin.required_source",
                "builtin.expected_tool",
            ],
        ),
    ]
    if existing is None:
        return await create_dataset(
            session,
            DatasetCreate(
                project_id=project_id,
                name="Demo Regression Suite",
                slug="demo-golden-set",
                description=(
                    "Representative behaviors compared across a trusted baseline and candidate."
                ),
                cases=case_payloads,
            ),
            workspace_id=workspace_id,
        )

    existing_names = {case.name for case in existing.cases}
    for payload in case_payloads:
        if payload.name not in existing_names:
            await create_dataset_case(
                session,
                existing.id,
                payload,
                workspace_id=workspace_id,
            )
    result = await session.execute(
        select(Dataset)
        .options(selectinload(Dataset.cases))
        .where(Dataset.id == existing.id)
        .execution_options(populate_existing=True)
    )
    return result.scalar_one()


async def _ensure_paired_demo_evidence(
    session: AsyncSession,
    *,
    settings: Settings,
    dataset,
    project_slug: str,
    baseline_version: str,
    candidate_version: str,
    workspace_id,
) -> list[str]:
    answers = {
        "explains-agentguard": (
            "AgentGuard captures traces and evaluates AI application behavior.",
            "AgentGuard monitors AI application runs.",
        ),
        "supports-release-decisions": (
            "AgentGuard stores execution telemetry for later inspection.",
            "AgentGuard compares evidence and produces auditable release decisions.",
        ),
        "records-execution-steps": (
            "AgentGuard records complete runs and their nested steps.",
            "AgentGuard records complete runs and their nested steps.",
        ),
    }
    source_ids = {
        "supports-release-decisions": "release-policy",
        "records-execution-steps": "instrumentation-guide",
    }
    trace_ids: list[str] = []
    for case in dataset.cases:
        case_answers = answers.get(case.name)
        if case_answers is None:
            continue
        for version, answer in zip(
            (baseline_version, candidate_version),
            case_answers,
            strict=True,
        ):
            trace = await _ensure_behavior_trace(
                session,
                settings=settings,
                project_slug=project_slug,
                version=version,
                case=case,
                answer=answer,
                source_id=source_ids.get(case.name, "agentguard-overview"),
                workspace_id=workspace_id,
            )
            trace_ids.append(str(trace.id))
            evaluator_names = case.meta.get("evaluators") or ["builtin.answer_contains"]
            for evaluator_name in evaluator_names:
                await evaluate_trace_against_case(
                    session,
                    trace=trace,
                    case=case,
                    evaluator_name=evaluator_name,
                    settings=settings,
                    workspace_id=workspace_id,
                )
    return trace_ids


async def _ensure_behavior_trace(
    session: AsyncSession,
    *,
    settings: Settings,
    project_slug: str,
    version: str,
    case,
    answer: str,
    source_id: str,
    workspace_id,
) -> Trace:
    external_trace_id = f"demo-paired-{case.name}-{version}"
    existing = await session.scalar(
        select(Trace)
        .options(selectinload(Trace.spans))
        .join(Project)
        .where(
            Trace.external_trace_id == external_trace_id,
            Project.workspace_id == workspace_id,
        )
    )
    if existing is not None:
        return existing

    started = utc_now()
    trace = await ingest_trace(
        session,
        TraceIngest(
            project_slug=project_slug,
            version=version,
            external_trace_id=external_trace_id,
            name=f"demo:{case.name}",
            status=RunStatus.OK,
            input={**case.input, "dataset_case_id": str(case.id)},
            output={"answer": answer},
            metadata={
                "source": "public_demo",
                "dataset_id": str(case.dataset_id),
                "dataset_case_id": str(case.id),
            },
            started_at=started,
            ended_at=started + timedelta(milliseconds=120),
            spans=[
                SpanIngest(
                    external_span_id="retrieve",
                    type=SpanType.RETRIEVER,
                    name="retrieve-policy",
                    status=RunStatus.OK,
                    input={"query": case.input.get("question")},
                    output={"documents": [{"id": source_id, "score": 0.93}]},
                    started_at=started,
                    ended_at=started + timedelta(milliseconds=35),
                ),
                SpanIngest(
                    external_span_id="policy-tool",
                    type=SpanType.TOOL,
                    name="policy_lookup",
                    status=RunStatus.OK,
                    input={"document_id": source_id},
                    output={"found": True},
                    started_at=started + timedelta(milliseconds=36),
                    ended_at=started + timedelta(milliseconds=48),
                ),
                SpanIngest(
                    external_span_id="generate",
                    type=SpanType.LLM,
                    name="generate-answer",
                    status=RunStatus.OK,
                    input={"question": case.input.get("question"), "source_ids": [source_id]},
                    output={"answer": answer},
                    provider="local",
                    model_name="demo-model",
                    started_at=started + timedelta(milliseconds=49),
                    ended_at=started + timedelta(milliseconds=120),
                ),
            ],
        ),
        settings,
        workspace_id=workspace_id,
    )
    result = await session.execute(
        select(Trace).options(selectinload(Trace.spans)).where(Trace.id == trace.id)
    )
    return result.scalar_one()
