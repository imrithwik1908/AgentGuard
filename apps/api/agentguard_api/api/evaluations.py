from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from agentguard_api.core.config import Settings, get_settings
from agentguard_api.db.session import get_session
from agentguard_api.models import Dataset, Project
from agentguard_api.schemas.evaluation import (
    EvaluationCreate,
    EvaluationJobCreate,
    EvaluationJobRead,
    EvaluationList,
    EvaluationOrchestrationRequest,
    EvaluationOrchestrationResponse,
    EvaluationRead,
    EvaluationSummary,
    FailureCluster,
    PairedVersionComparison,
    ReleaseDecision,
    VersionComparison,
)
from agentguard_api.services.errors import NotFoundError
from agentguard_api.services.evaluation_jobs import (
    enqueue_evaluation_job,
    enqueue_evaluation_job_for_processing,
    get_evaluation_job,
)
from agentguard_api.services.evaluations import (
    compare_versions,
    create_evaluation,
    create_status_evaluation,
    create_trace_health_evaluations,
    decide_release,
    list_evaluations,
    orchestration_job_request_id,
    paired_case_comparison,
    summarize_version,
)
from agentguard_api.services.security import AuthContext, get_auth_context

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


def _case_evaluators(dataset: Dataset) -> list[str]:
    names: set[str] = {"builtin.runtime_success"}
    for case in dataset.cases:
        configured = case.meta.get("evaluators")
        if isinstance(configured, list) and configured:
            names.update(str(name) for name in configured)
            continue
        if case.expected_substring or case.expected_output or case.meta.get("semantic_requirement"):
            names.add("builtin.required_content")
        if case.meta.get("required_sources") or case.meta.get("expected_document_ids"):
            names.add("builtin.required_source")
        if case.meta.get("expected_tool") or case.meta.get("expected_tools"):
            names.add("builtin.expected_tool")
        if case.meta.get("forbidden_tools"):
            names.add("builtin.forbidden_tool")
        if case.meta.get("latency_budget_ms"):
            names.add("builtin.latency")
    return sorted(names)


def _failure_clusters(regressed) -> list[FailureCluster]:
    grouped: dict[tuple[str, str], list] = {}
    for item in regressed:
        if isinstance(item, dict):
            analysis = item.get("failure_analysis") or {}
            evaluator_name = str(item.get("evaluator_name") or "unknown")
        else:
            analysis = item.failure_analysis or {}
            evaluator_name = item.evaluator_name
        stage = str(analysis.get("likely_failure_stage") or "unknown")
        key = (stage, evaluator_name)
        grouped.setdefault(key, []).append(item)

    clusters: list[FailureCluster] = []
    stage_labels = {
        "retrieval": "Retrieval mismatch",
        "generation": "Answer generation",
        "tool": "Tool behavior",
        "workflow": "Workflow execution",
        "unknown": "Unclassified regression",
    }
    for (stage, evaluator_name), items in sorted(
        grouped.items(),
        key=lambda entry: (-len(entry[1]), entry[0][0], entry[0][1]),
    ):
        label = stage_labels.get(stage, "Unclassified regression")
        clusters.append(
            FailureCluster(
                label=label,
                summary=(
                    f"{len(items)} regression(s) grouped by {stage} evidence from {evaluator_name}."
                ),
                likely_failure_stage=stage,
                case_count=len(items),
                evaluator_names=sorted(
                    {
                        str(
                            item.get("evaluator_name")
                            if isinstance(item, dict)
                            else item.evaluator_name
                        )
                        for item in items
                    }
                ),
                dataset_case_ids=[
                    item.get("dataset_case_id") if isinstance(item, dict) else item.dataset_case_id
                    for item in items
                ],
            )
        )
    return clusters


def _paired_response(comparison, buckets) -> PairedVersionComparison:
    comparable_case_count = (
        len(buckets["regressed"]) + len(buckets["improved"]) + len(buckets["unchanged"])
    )
    total_case_count = comparable_case_count + len(buckets["not_comparable"])
    comparison_coverage = (
        (Decimal(comparable_case_count) / Decimal(total_case_count)).quantize(Decimal("0.0001"))
        if total_case_count
        else None
    )
    return PairedVersionComparison(
        **comparison.model_dump(),
        regressed=buckets["regressed"],
        improved=buckets["improved"],
        unchanged=buckets["unchanged"],
        not_comparable=buckets["not_comparable"],
        failure_clusters=_failure_clusters(buckets["regressed"]),
        comparable_case_count=comparable_case_count,
        total_case_count=total_case_count,
        comparison_coverage=comparison_coverage,
    )


@router.post(
    "/jobs",
    response_model=EvaluationJobRead,
    status_code=202,
)
async def create_evaluation_job(
    payload: EvaluationJobCreate,
    session: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
    settings: Settings = Depends(get_settings),
):
    job = await enqueue_evaluation_job(
        session,
        payload,
        workspace_id=auth.workspace_id,
    )
    return await enqueue_evaluation_job_for_processing(
        session,
        job,
        settings=settings,
        workspace_id=auth.workspace_id,
    )


@router.post(
    "/orchestrate",
    response_model=EvaluationOrchestrationResponse,
    status_code=202,
)
async def orchestrate_evaluation(
    payload: EvaluationOrchestrationRequest,
    session: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
    settings: Settings = Depends(get_settings),
):
    dataset = await session.scalar(
        select(Dataset)
        .options(selectinload(Dataset.cases))
        .join(Project)
        .where(Dataset.id == payload.dataset_id)
        .where(Project.workspace_id == auth.workspace_id)
    )
    if dataset is None:
        raise NotFoundError("dataset was not found")
    evaluator_names = payload.evaluator_names or (_case_evaluators(dataset) if dataset else [])
    jobs: list[EvaluationJobRead] = []
    for version_id in (payload.baseline_version_id, payload.candidate_version_id):
        for evaluator_name in evaluator_names:
            job = await enqueue_evaluation_job(
                session,
                EvaluationJobCreate(
                    dataset_id=payload.dataset_id,
                    application_version_id=version_id,
                    evaluator_name=evaluator_name,
                    request_id=orchestration_job_request_id(
                        payload.request_id,
                        version_id,
                        evaluator_name,
                    ),
                    max_attempts=payload.max_attempts,
                ),
                workspace_id=auth.workspace_id,
            )
            queued = await enqueue_evaluation_job_for_processing(
                session,
                job,
                settings=settings,
                workspace_id=auth.workspace_id,
            )
            jobs.append(EvaluationJobRead.model_validate(queued))

    all_jobs_finished = all(job.status.value in {"COMPLETED", "PARTIAL", "FAILED"} for job in jobs)
    if not all_jobs_finished:
        return EvaluationOrchestrationResponse(
            status="QUEUED",
            dataset_id=payload.dataset_id,
            baseline_version_id=payload.baseline_version_id,
            candidate_version_id=payload.candidate_version_id,
            evaluator_names=evaluator_names,
            jobs=jobs,
        )

    comparison = await compare_versions(
        session,
        baseline_version_id=payload.baseline_version_id,
        candidate_version_id=payload.candidate_version_id,
        workspace_id=auth.workspace_id,
    )
    buckets = await paired_case_comparison(
        session,
        baseline_version_id=payload.baseline_version_id,
        candidate_version_id=payload.candidate_version_id,
        workspace_id=auth.workspace_id,
    )
    release_decision = await decide_release(
        session,
        baseline_version_id=payload.baseline_version_id,
        candidate_version_id=payload.candidate_version_id,
        minimum_pass_rate=Decimal("0.8000"),
        maximum_regressions=0,
        allowed_score_drop=Decimal("0.0500"),
        workspace_id=auth.workspace_id,
    )
    return EvaluationOrchestrationResponse(
        status="COMPLETED",
        dataset_id=payload.dataset_id,
        baseline_version_id=payload.baseline_version_id,
        candidate_version_id=payload.candidate_version_id,
        evaluator_names=evaluator_names,
        jobs=jobs,
        comparison=_paired_response(comparison, buckets),
        release_decision=release_decision,
    )


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
    return _paired_response(comparison, buckets)


@router.get("/release-decision", response_model=ReleaseDecision)
async def read_release_decision(
    baseline_version_id: UUID,
    candidate_version_id: UUID,
    minimum_pass_rate: Decimal = Query(default=Decimal("0.8000"), ge=0, le=1),
    maximum_regressions: int = Query(default=0, ge=0),
    allowed_score_drop: Decimal = Query(default=Decimal("0.0000"), ge=0, le=1),
    minimum_evaluation_coverage: Decimal = Query(default=Decimal("1.0000"), ge=0, le=1),
    required_evaluator: list[str] | None = Query(default=None),
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
        minimum_evaluation_coverage=minimum_evaluation_coverage.quantize(Decimal("0.0001")),
        required_evaluator_names=required_evaluator or [],
        workspace_id=auth.workspace_id,
    )
