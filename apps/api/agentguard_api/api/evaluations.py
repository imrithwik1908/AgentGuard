from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from agentguard_api.core.config import Settings, get_settings
from agentguard_api.db.session import get_session
from agentguard_api.schemas.evaluation import (
    EvaluationCreate,
    EvaluationJobCreate,
    EvaluationJobRead,
    EvaluationList,
    EvaluationRead,
    EvaluationSummary,
    PairedVersionComparison,
    ReleaseDecision,
    VersionComparison,
)
from agentguard_api.services.evaluation_jobs import (
    enqueue_evaluation_job,
    get_evaluation_job,
    process_evaluation_job,
)
from agentguard_api.services.evaluations import (
    compare_versions,
    create_evaluation,
    create_status_evaluation,
    create_trace_health_evaluations,
    decide_release,
    list_evaluations,
    paired_case_comparison,
    summarize_version,
)
from agentguard_api.services.security import AuthContext, get_auth_context

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


@router.post("/jobs", response_model=EvaluationJobRead, status_code=202)
async def create_evaluation_job(
    payload: EvaluationJobCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    auth: AuthContext = Depends(get_auth_context),
):
    job = await enqueue_evaluation_job(session, payload, workspace_id=auth.workspace_id)
    background_tasks.add_task(
        process_evaluation_job,
        job.id,
        settings=settings,
        workspace_id=auth.workspace_id,
    )
    return job


@router.get("/jobs/{job_id}", response_model=EvaluationJobRead)
async def read_evaluation_job(
    job_id: UUID,
    session: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
):
    return await get_evaluation_job(session, job_id, workspace_id=auth.workspace_id)


@router.post("", response_model=EvaluationRead, status_code=201)
async def create_evaluation_result(
    payload: EvaluationCreate,
    session: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
):
    return await create_evaluation(session, payload, workspace_id=auth.workspace_id)


@router.post("/traces/{trace_id}/status-check", response_model=EvaluationRead, status_code=201)
async def create_trace_status_evaluation(
    trace_id: UUID,
    session: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
):
    return await create_status_evaluation(session, trace_id, workspace_id=auth.workspace_id)


@router.post(
    "/traces/{trace_id}/health-check",
    response_model=list[EvaluationRead],
    status_code=201,
)
async def create_trace_health_evaluation(
    trace_id: UUID,
    latency_budget_ms: int = Query(default=2_000, ge=1, le=120_000),
    session: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
):
    return await create_trace_health_evaluations(
        session,
        trace_id,
        latency_budget_ms=latency_budget_ms,
        workspace_id=auth.workspace_id,
    )


@router.get("", response_model=EvaluationList)
async def read_evaluations(
    project_id: UUID | None = None,
    application_version_id: UUID | None = None,
    trace_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
) -> EvaluationList:
    evaluations, total = await list_evaluations(
        session,
        project_id=project_id,
        application_version_id=application_version_id,
        trace_id=trace_id,
        workspace_id=auth.workspace_id,
        limit=limit,
        offset=offset,
    )
    return EvaluationList(items=evaluations, limit=limit, offset=offset, total=total)


@router.get("/summary/{application_version_id}", response_model=EvaluationSummary)
async def read_evaluation_summary(
    application_version_id: UUID,
    session: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
):
    return await summarize_version(session, application_version_id, workspace_id=auth.workspace_id)


@router.get("/compare", response_model=VersionComparison)
async def read_version_comparison(
    baseline_version_id: UUID,
    candidate_version_id: UUID,
    session: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
):
    return await compare_versions(
        session,
        baseline_version_id=baseline_version_id,
        candidate_version_id=candidate_version_id,
        workspace_id=auth.workspace_id,
    )


@router.get("/compare/paired", response_model=PairedVersionComparison)
async def read_paired_version_comparison(
    baseline_version_id: UUID,
    candidate_version_id: UUID,
    session: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
):
    comparison = await compare_versions(
        session,
        baseline_version_id=baseline_version_id,
        candidate_version_id=candidate_version_id,
        workspace_id=auth.workspace_id,
    )
    buckets = await paired_case_comparison(
        session,
        baseline_version_id=baseline_version_id,
        candidate_version_id=candidate_version_id,
        workspace_id=auth.workspace_id,
    )
    return PairedVersionComparison(
        **comparison.model_dump(),
        regressed=buckets["regressed"],
        improved=buckets["improved"],
        unchanged=buckets["unchanged"],
        not_comparable=buckets["not_comparable"],
    )


@router.get("/release-decision", response_model=ReleaseDecision)
async def read_release_decision(
    baseline_version_id: UUID,
    candidate_version_id: UUID,
    minimum_pass_rate: Decimal = Query(default=Decimal("0.8000"), ge=0, le=1),
    maximum_regressions: int = Query(default=0, ge=0),
    allowed_score_drop: Decimal = Query(default=Decimal("0.0000"), ge=0, le=1),
    session: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
):
    return await decide_release(
        session,
        baseline_version_id=baseline_version_id,
        candidate_version_id=candidate_version_id,
        minimum_pass_rate=minimum_pass_rate.quantize(Decimal("0.0001")),
        maximum_regressions=maximum_regressions,
        allowed_score_drop=allowed_score_drop.quantize(Decimal("0.0001")),
        workspace_id=auth.workspace_id,
    )
