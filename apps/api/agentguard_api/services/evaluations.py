import hashlib
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from agentguard_api.models import (
    ApplicationVersion,
    DatasetCase,
    EvaluationJob,
    EvaluationJobCase,
    EvaluationJobStatus,
    EvaluationMethod,
    EvaluationResult,
    EvaluationStatus,
    Project,
    Trace,
)
from agentguard_api.models.enums import RunStatus
from agentguard_api.schemas.evaluation import (
    EvaluationCreate,
    EvaluationSummary,
    ReleaseDecision,
    VersionComparison,
)
from agentguard_api.services.errors import ConflictError, NotFoundError, ValidationError
from agentguard_api.services.failure_analysis import analyze_pair


def orchestration_job_request_id(
    request_id: str | None,
    version_id: UUID,
    evaluator_name: str,
) -> str | None:
    if request_id is None:
        return None
    digest = hashlib.sha256(f"{request_id}:{version_id}:{evaluator_name}".encode()).hexdigest()
    return f"orchestration:{digest}"


def _regression_tolerance(
    evaluation: EvaluationResult,
) -> Decimal:
    if evaluation.method == EvaluationMethod.LLM_JUDGE:
        return Decimal("0.0500")

    return Decimal("0.0500")


TERMINAL_JOB_STATUSES = {
    EvaluationJobStatus.COMPLETED,
    EvaluationJobStatus.PARTIAL,
}


def _supports_fail_to_fail_worsening(evaluation: EvaluationResult) -> bool:
    return evaluation.method in {
        EvaluationMethod.LLM_JUDGE,
        EvaluationMethod.RETRIEVAL,
    }


def _derive_status(
    *,
    score: Decimal,
    threshold: Decimal | None,
    status: EvaluationStatus | None,
    passed: bool | None,
) -> tuple[EvaluationStatus, bool]:
    if status is not None and passed is not None:
        if (status == EvaluationStatus.PASS) != passed:
            raise ValidationError("evaluation status and passed flag disagree")
        return status, passed

    if status is not None:
        return status, status == EvaluationStatus.PASS

    if passed is not None:
        return EvaluationStatus.PASS if passed else EvaluationStatus.FAIL, passed

    if threshold is None:
        return EvaluationStatus.PASS, True
    passed_from_score = score >= threshold
    return EvaluationStatus.PASS if passed_from_score else EvaluationStatus.FAIL, passed_from_score


def _default_method(evaluator_name: str) -> EvaluationMethod:
    if evaluator_name.startswith("builtin.trace_health.evidence"):
        return EvaluationMethod.INSTRUMENTATION_ONLY
    if (
        evaluator_name.startswith("builtin.trace_health")
        or evaluator_name == "builtin.trace_status"
    ):
        return EvaluationMethod.DETERMINISTIC_OPERATIONAL
    if "retrieval" in evaluator_name:
        return EvaluationMethod.RETRIEVAL
    return EvaluationMethod.DETERMINISTIC_BEHAVIORAL


async def create_evaluation(
    session: AsyncSession,
    payload: EvaluationCreate,
    *,
    workspace_id: UUID | None = None,
) -> EvaluationResult:
    trace_query = select(Trace).join(Project).where(Trace.id == payload.trace_id)
    if workspace_id is not None:
        trace_query = trace_query.where(Project.workspace_id == workspace_id)
    trace = await session.scalar(trace_query)
    if trace is None:
        raise NotFoundError("trace was not found", metadata={"trace_id": str(payload.trace_id)})

    status, passed = _derive_status(
        score=payload.score,
        threshold=payload.threshold,
        status=payload.status,
        passed=payload.passed,
    )
    result = EvaluationResult(
        project_id=trace.project_id,
        dataset_id=payload.dataset_id,
        dataset_case_id=payload.dataset_case_id,
        application_version_id=trace.application_version_id,
        trace_id=trace.id,
        evaluator_name=payload.evaluator_name,
        evaluator_version=payload.evaluator_version,
        method=payload.method or _default_method(payload.evaluator_name),
        rubric=payload.rubric,
        judge_model=payload.judge_model,
        score=payload.score,
        threshold=payload.threshold,
        status=status,
        passed=passed,
        label=payload.label,
        explanation=payload.explanation,
        meta=payload.metadata,
    )
    session.add(result)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError(
            "evaluation already exists for this trace and evaluator",
            metadata={"trace_id": str(payload.trace_id), "evaluator_name": payload.evaluator_name},
        ) from exc
    await session.refresh(result)
    return result


async def create_status_evaluation(
    session: AsyncSession,
    trace_id: UUID,
    *,
    workspace_id: UUID | None = None,
) -> EvaluationResult:
    trace_query = select(Trace).options(selectinload(Trace.spans)).where(Trace.id == trace_id)
    if workspace_id is not None:
        trace_query = trace_query.join(Project).where(Project.workspace_id == workspace_id)
    trace = await session.scalar(trace_query)
    if trace is None:
        raise NotFoundError("trace was not found", metadata={"trace_id": str(trace_id)})

    passed = trace.status == RunStatus.OK
    payload = EvaluationCreate(
        trace_id=trace.id,
        evaluator_name="builtin.trace_status",
        method=EvaluationMethod.DETERMINISTIC_OPERATIONAL,
        rubric={"pass_condition": "trace.status == OK"},
        score=Decimal("1.0000") if passed else Decimal("0.0000"),
        threshold=Decimal("1.0000"),
        passed=passed,
        label="Trace completed successfully" if passed else "Trace ended with an error",
        explanation=(
            "Built-in deterministic evaluator: PASS when trace.status is OK, FAIL otherwise."
        ),
        metadata={"trace_status": trace.status.value},
    )
    return await create_evaluation(session, payload, workspace_id=workspace_id)


async def _existing_evaluation(
    session: AsyncSession,
    *,
    trace_id: UUID,
    evaluator_name: str,
) -> EvaluationResult | None:
    return await session.scalar(
        select(EvaluationResult).where(
            EvaluationResult.trace_id == trace_id,
            EvaluationResult.evaluator_name == evaluator_name,
        )
    )


async def _create_or_get_evaluation(
    session: AsyncSession,
    payload: EvaluationCreate,
    *,
    workspace_id: UUID | None = None,
) -> EvaluationResult:
    existing = await _existing_evaluation(
        session,
        trace_id=payload.trace_id,
        evaluator_name=payload.evaluator_name,
    )
    if existing is not None:
        return existing
    try:
        return await create_evaluation(session, payload, workspace_id=workspace_id)
    except ConflictError:
        existing_after_conflict = await _existing_evaluation(
            session,
            trace_id=payload.trace_id,
            evaluator_name=payload.evaluator_name,
        )
        if existing_after_conflict is None:
            raise
        return existing_after_conflict


async def create_trace_health_evaluations(
    session: AsyncSession,
    trace_id: UUID,
    *,
    latency_budget_ms: int = 2_000,
    workspace_id: UUID | None = None,
) -> list[EvaluationResult]:
    trace_query = select(Trace).options(selectinload(Trace.spans)).where(Trace.id == trace_id)
    if workspace_id is not None:
        trace_query = trace_query.join(Project).where(Project.workspace_id == workspace_id)
    trace = await session.scalar(trace_query)
    if trace is None:
        raise NotFoundError("trace was not found", metadata={"trace_id": str(trace_id)})

    error_spans = [span for span in trace.spans if span.status == RunStatus.ERROR or span.error]
    evidence_spans = [
        span
        for span in trace.spans
        if span.input is not None or span.output is not None or span.error is not None
    ]
    latency_score = (
        Decimal("1.0000")
        if trace.duration_ms <= latency_budget_ms
        else max(
            Decimal("0.0000"),
            (Decimal(latency_budget_ms) / Decimal(trace.duration_ms)).quantize(Decimal("0.0001")),
        )
    )
    evidence_score = (
        Decimal(len(evidence_spans)) / Decimal(len(trace.spans))
        if trace.spans
        else Decimal("0.0000")
    ).quantize(Decimal("0.0001"))

    payloads = [
        EvaluationCreate(
            trace_id=trace.id,
            evaluator_name="builtin.trace_health.status",
            method=EvaluationMethod.DETERMINISTIC_OPERATIONAL,
            rubric={"pass_condition": "trace.status == OK"},
            score=Decimal("1.0000") if trace.status == RunStatus.OK else Decimal("0.0000"),
            threshold=Decimal("1.0000"),
            passed=trace.status == RunStatus.OK,
            label="Run completed" if trace.status == RunStatus.OK else "Run failed",
            explanation=(
                "Checks whether the top-level trace status says the application run completed."
            ),
            metadata={"trace_status": trace.status.value},
        ),
        EvaluationCreate(
            trace_id=trace.id,
            evaluator_name="builtin.trace_health.error_spans",
            method=EvaluationMethod.DETERMINISTIC_OPERATIONAL,
            rubric={"pass_condition": "no span has ERROR status or captured error"},
            score=Decimal("1.0000") if not error_spans else Decimal("0.0000"),
            threshold=Decimal("1.0000"),
            passed=not error_spans,
            label="No nested span errors" if not error_spans else "Nested span errors found",
            explanation=("Checks whether any internal step captured an exception or ERROR status."),
            metadata={
                "error_span_count": len(error_spans),
                "error_spans": [
                    {"id": str(span.id), "name": span.name, "type": span.type.value}
                    for span in error_spans
                ],
            },
        ),
        EvaluationCreate(
            trace_id=trace.id,
            evaluator_name="builtin.trace_health.latency_budget",
            method=EvaluationMethod.DETERMINISTIC_OPERATIONAL,
            rubric={"latency_budget_ms": latency_budget_ms, "threshold": "0.8000"},
            score=latency_score,
            threshold=Decimal("0.8000"),
            passed=latency_score >= Decimal("0.8000"),
            label=(
                "Latency inside budget"
                if trace.duration_ms <= latency_budget_ms
                else "Latency exceeded budget"
            ),
            explanation=("Scores the trace duration against a deterministic latency budget."),
            metadata={
                "duration_ms": trace.duration_ms,
                "latency_budget_ms": latency_budget_ms,
            },
        ),
        EvaluationCreate(
            trace_id=trace.id,
            evaluator_name="builtin.trace_health.evidence",
            method=EvaluationMethod.INSTRUMENTATION_ONLY,
            rubric={
                "pass_condition": (
                    "at least half of spans contain input, output, or error evidence"
                )
            },
            score=evidence_score,
            threshold=Decimal("0.5000"),
            passed=evidence_score >= Decimal("0.5000"),
            label=(
                "Trace has inspectable evidence"
                if evidence_score >= Decimal("0.5000")
                else "Trace is thin"
            ),
            explanation=(
                "Checks whether spans include inputs, outputs, or error payloads that make "
                "the run debuggable."
            ),
            metadata={
                "span_count": len(trace.spans),
                "evidence_span_count": len(evidence_spans),
            },
        ),
    ]
    return [
        await _create_or_get_evaluation(session, payload, workspace_id=workspace_id)
        for payload in payloads
    ]


def evaluation_list_query(
    *,
    project_id: UUID | None = None,
    application_version_id: UUID | None = None,
    trace_id: UUID | None = None,
    workspace_id: UUID | None = None,
) -> Select:
    stmt = select(EvaluationResult)
    if workspace_id is not None:
        stmt = stmt.join(Project, Project.id == EvaluationResult.project_id).where(
            Project.workspace_id == workspace_id
        )
    if project_id:
        stmt = stmt.where(EvaluationResult.project_id == project_id)
    if application_version_id:
        stmt = stmt.where(EvaluationResult.application_version_id == application_version_id)
    if trace_id:
        stmt = stmt.where(EvaluationResult.trace_id == trace_id)
    return stmt.order_by(EvaluationResult.created_at.desc())


async def list_evaluations(
    session: AsyncSession,
    *,
    project_id: UUID | None,
    application_version_id: UUID | None,
    trace_id: UUID | None,
    workspace_id: UUID | None = None,
    limit: int,
    offset: int,
) -> tuple[list[EvaluationResult], int]:
    base = evaluation_list_query(
        project_id=project_id,
        application_version_id=application_version_id,
        trace_id=trace_id,
        workspace_id=workspace_id,
    )
    total = await session.scalar(select(func.count()).select_from(base.subquery()))
    result = await session.execute(base.limit(limit).offset(offset))
    return list(result.scalars()), int(total or 0)


async def summarize_version(
    session: AsyncSession,
    version_id: UUID,
    *,
    workspace_id: UUID | None = None,
) -> EvaluationSummary:
    version_query = (
        select(ApplicationVersion).join(Project).where(ApplicationVersion.id == version_id)
    )
    if workspace_id is not None:
        version_query = version_query.where(Project.workspace_id == workspace_id)
    version = await session.scalar(version_query)
    if version is None:
        raise NotFoundError(
            "application version was not found",
            metadata={"version_id": str(version_id)},
        )

    evaluation_count = await session.scalar(
        select(func.count()).where(EvaluationResult.application_version_id == version_id)
    )
    trace_count = await session.scalar(
        select(func.count(func.distinct(EvaluationResult.trace_id))).where(
            EvaluationResult.application_version_id == version_id
        )
    )
    pass_count = await session.scalar(
        select(func.count()).where(
            EvaluationResult.application_version_id == version_id,
            EvaluationResult.status == EvaluationStatus.PASS,
        )
    )
    fail_count = await session.scalar(
        select(func.count()).where(
            EvaluationResult.application_version_id == version_id,
            EvaluationResult.status == EvaluationStatus.FAIL,
        )
    )
    error_count = await session.scalar(
        select(func.count()).where(
            EvaluationResult.application_version_id == version_id,
            EvaluationResult.status == EvaluationStatus.ERROR,
        )
    )
    average_score = await session.scalar(
        select(func.avg(EvaluationResult.score)).where(
            EvaluationResult.application_version_id == version_id
        )
    )

    evaluation_count_int = int(evaluation_count or 0)
    pass_count_int = int(pass_count or 0)
    pass_rate = (
        (Decimal(pass_count_int) / Decimal(evaluation_count_int)).quantize(Decimal("0.0001"))
        if evaluation_count_int
        else None
    )

    return EvaluationSummary(
        project_id=version.project_id,
        application_version_id=version.id,
        evaluation_count=evaluation_count_int,
        trace_count=int(trace_count or 0),
        pass_count=pass_count_int,
        fail_count=int(fail_count or 0),
        error_count=int(error_count or 0),
        pass_rate=pass_rate,
        average_score=(
            Decimal(str(average_score)).quantize(Decimal("0.0001"))
            if average_score is not None
            else None
        ),
    )


def _summary_from_evaluations(
    *,
    project_id: UUID,
    version_id: UUID,
    evaluations: list[EvaluationResult],
) -> EvaluationSummary:
    evaluation_count = len(evaluations)
    pass_count = sum(1 for item in evaluations if item.status == EvaluationStatus.PASS)
    fail_count = sum(1 for item in evaluations if item.status == EvaluationStatus.FAIL)
    error_count = sum(1 for item in evaluations if item.status == EvaluationStatus.ERROR)
    average_score = (
        (
            sum((item.score for item in evaluations), Decimal("0.0000")) / Decimal(evaluation_count)
        ).quantize(Decimal("0.0001"))
        if evaluation_count
        else None
    )
    pass_rate = (
        (Decimal(pass_count) / Decimal(evaluation_count)).quantize(Decimal("0.0001"))
        if evaluation_count
        else None
    )
    return EvaluationSummary(
        project_id=project_id,
        application_version_id=version_id,
        evaluation_count=evaluation_count,
        trace_count=len({item.trace_id for item in evaluations}),
        pass_count=pass_count,
        fail_count=fail_count,
        error_count=error_count,
        pass_rate=pass_rate,
        average_score=average_score,
    )


async def _latest_job_case_evaluations(
    session: AsyncSession,
    *,
    baseline_version_id: UUID,
    candidate_version_id: UUID,
    workspace_id: UUID | None = None,
) -> list[tuple[EvaluationJob, EvaluationJobCase, EvaluationResult]]:
    stmt = (
        select(EvaluationJob)
        .options(selectinload(EvaluationJob.cases))
        .where(
            EvaluationJob.application_version_id.in_([baseline_version_id, candidate_version_id]),
            EvaluationJob.status.in_(TERMINAL_JOB_STATUSES),
        )
        .order_by(EvaluationJob.created_at.desc())
    )
    if workspace_id is not None:
        stmt = stmt.join(Project, Project.id == EvaluationJob.project_id).where(
            Project.workspace_id == workspace_id
        )

    jobs = list((await session.execute(stmt)).scalars())
    latest_jobs: dict[tuple[UUID, UUID, str], EvaluationJob] = {}
    for job in jobs:
        key = (job.dataset_id, job.application_version_id, job.evaluator_name)
        latest_jobs.setdefault(key, job)

    evaluation_ids = [
        case.evaluation_result_id
        for job in latest_jobs.values()
        for case in job.cases
        if case.evaluation_result_id is not None
    ]
    if not evaluation_ids:
        return []

    evaluations = list(
        (
            await session.execute(
                select(EvaluationResult).where(EvaluationResult.id.in_(evaluation_ids))
            )
        ).scalars()
    )
    evaluation_by_id = {evaluation.id: evaluation for evaluation in evaluations}
    rows: list[tuple[EvaluationJob, EvaluationJobCase, EvaluationResult]] = []
    for job in latest_jobs.values():
        for case in job.cases:
            if case.evaluation_result_id is None:
                continue
            evaluation = evaluation_by_id.get(case.evaluation_result_id)
            if evaluation is not None:
                rows.append((job, case, evaluation))
    return rows


async def _latest_direct_evaluations(
    session: AsyncSession,
    *,
    baseline_version_id: UUID,
    candidate_version_id: UUID,
    workspace_id: UUID | None = None,
) -> list[tuple[None, None, EvaluationResult]]:
    stmt = select(EvaluationResult).where(
        EvaluationResult.application_version_id.in_([baseline_version_id, candidate_version_id]),
        EvaluationResult.dataset_case_id.is_not(None),
    )
    if workspace_id is not None:
        stmt = stmt.join(Project, Project.id == EvaluationResult.project_id).where(
            Project.workspace_id == workspace_id
        )
    rows = list((await session.execute(stmt)).scalars())
    latest: dict[tuple[UUID, UUID, str], EvaluationResult] = {}
    for row in rows:
        if row.dataset_case_id is None:
            continue
        key = (row.dataset_case_id, row.application_version_id, row.evaluator_name)
        previous = latest.get(key)
        if previous is None or row.created_at > previous.created_at:
            latest[key] = row
    return [(None, None, evaluation) for evaluation in latest.values()]


async def _comparison_evidence(
    session: AsyncSession,
    *,
    baseline_version_id: UUID,
    candidate_version_id: UUID,
    workspace_id: UUID | None = None,
) -> tuple[
    list[tuple[EvaluationJob | None, EvaluationJobCase | None, EvaluationResult]],
    bool,
]:
    job_rows = await _latest_job_case_evaluations(
        session,
        baseline_version_id=baseline_version_id,
        candidate_version_id=candidate_version_id,
        workspace_id=workspace_id,
    )
    if job_rows:
        return job_rows, True
    return (
        await _latest_direct_evaluations(
            session,
            baseline_version_id=baseline_version_id,
            candidate_version_id=candidate_version_id,
            workspace_id=workspace_id,
        ),
        False,
    )


async def compare_versions(
    session: AsyncSession,
    *,
    baseline_version_id: UUID,
    candidate_version_id: UUID,
    workspace_id: UUID | None = None,
) -> VersionComparison:
    version_stmt = select(ApplicationVersion).join(Project)
    if workspace_id is not None:
        version_stmt = version_stmt.where(Project.workspace_id == workspace_id)
    baseline_version = await session.scalar(
        version_stmt.where(ApplicationVersion.id == baseline_version_id)
    )
    candidate_version = await session.scalar(
        version_stmt.where(ApplicationVersion.id == candidate_version_id)
    )
    if baseline_version is None:
        raise NotFoundError(
            "baseline application version was not found",
            metadata={"baseline_version_id": str(baseline_version_id)},
        )
    if candidate_version is None:
        raise NotFoundError(
            "candidate application version was not found",
            metadata={"candidate_version_id": str(candidate_version_id)},
        )
    if baseline_version.project_id != candidate_version.project_id:
        raise ValidationError("versions must belong to the same project to compare them")

    evidence, _ = await _comparison_evidence(
        session,
        baseline_version_id=baseline_version_id,
        candidate_version_id=candidate_version_id,
        workspace_id=workspace_id,
    )
    if evidence:
        baseline_evaluations = [
            evaluation
            for _, _, evaluation in evidence
            if evaluation.application_version_id == baseline_version_id
        ]
        candidate_evaluations = [
            evaluation
            for _, _, evaluation in evidence
            if evaluation.application_version_id == candidate_version_id
        ]
        baseline = _summary_from_evaluations(
            project_id=baseline_version.project_id,
            version_id=baseline_version_id,
            evaluations=baseline_evaluations,
        )
        candidate = _summary_from_evaluations(
            project_id=baseline_version.project_id,
            version_id=candidate_version_id,
            evaluations=candidate_evaluations,
        )
    else:
        baseline = await summarize_version(session, baseline_version_id, workspace_id=workspace_id)
        candidate = await summarize_version(
            session, candidate_version_id, workspace_id=workspace_id
        )
    score_delta = (
        (candidate.average_score - baseline.average_score).quantize(Decimal("0.0001"))
        if candidate.average_score is not None and baseline.average_score is not None
        else None
    )
    pass_rate_delta = (
        (candidate.pass_rate - baseline.pass_rate).quantize(Decimal("0.0001"))
        if candidate.pass_rate is not None and baseline.pass_rate is not None
        else None
    )
    return VersionComparison(
        project_id=baseline_version.project_id,
        baseline_version_id=baseline_version_id,
        candidate_version_id=candidate_version_id,
        baseline=baseline,
        candidate=candidate,
        score_delta=score_delta,
        pass_rate_delta=pass_rate_delta,
        regression_count_delta=candidate.fail_count - baseline.fail_count,
    )


async def paired_case_comparison(
    session: AsyncSession,
    *,
    baseline_version_id: UUID,
    candidate_version_id: UUID,
    workspace_id: UUID | None = None,
) -> dict[str, list[dict]]:
    await compare_versions(
        session,
        baseline_version_id=baseline_version_id,
        candidate_version_id=candidate_version_id,
        workspace_id=workspace_id,
    )
    rows, job_scoped = await _comparison_evidence(
        session,
        baseline_version_id=baseline_version_id,
        candidate_version_id=candidate_version_id,
        workspace_id=workspace_id,
    )
    grouped: dict[tuple[UUID | None, str], dict[str, EvaluationResult | UUID | None]] = {}
    for job, job_case, row in rows:
        key = (row.dataset_case_id, row.evaluator_name)
        side = "baseline" if row.application_version_id == baseline_version_id else "candidate"
        current = grouped.setdefault(key, {})
        current[side] = row
        if job_scoped:
            current[f"{side}_job_id"] = job.id if job else None
            current[f"{side}_job_case_id"] = job_case.id if job_case else None

    buckets: dict[str, list[dict]] = {
        "regressed": [],
        "improved": [],
        "unchanged": [],
        "not_comparable": [],
    }
    for (dataset_case_id, evaluator_name), pair in grouped.items():
        baseline_eval = pair.get("baseline")
        candidate_eval = pair.get("candidate")
        baseline_eval = baseline_eval if isinstance(baseline_eval, EvaluationResult) else None
        candidate_eval = candidate_eval if isinstance(candidate_eval, EvaluationResult) else None
        if baseline_eval is None or candidate_eval is None:
            classification = "not_comparable"
            explanation = "This case has evaluation evidence for only one version."
        elif baseline_eval.passed and not candidate_eval.passed:
            classification = "regressed"
            explanation = "The case passed in the baseline but failed in the candidate."
        elif not baseline_eval.passed and candidate_eval.passed:
            classification = "improved"
            explanation = "The case failed in the baseline but passed in the candidate."
        elif (
            not baseline_eval.passed
            and not candidate_eval.passed
            and not _supports_fail_to_fail_worsening(candidate_eval)
        ):
            classification = "unchanged"
            explanation = (
                "Both versions failed this deterministic check; "
                "no supported worsening was detected."
            )
        elif baseline_eval.score - candidate_eval.score >= _regression_tolerance(candidate_eval):
            classification = "regressed"
            explanation = (
                "The candidate score decreased meaningfully for the same test case and evaluator."
            )
        elif candidate_eval.score - baseline_eval.score >= _regression_tolerance(candidate_eval):
            classification = "improved"
            explanation = (
                "The candidate score improved meaningfully for the same test case and evaluator."
            )
        else:
            classification = "unchanged"
            explanation = "The paired case produced equivalent evaluation evidence."
        buckets[classification].append(
            {
                "dataset_case_id": dataset_case_id,
                "evaluator_name": evaluator_name,
                "baseline_evaluation_id": baseline_eval.id if baseline_eval else None,
                "candidate_evaluation_id": candidate_eval.id if candidate_eval else None,
                "baseline_evaluation_job_id": pair.get("baseline_job_id"),
                "candidate_evaluation_job_id": pair.get("candidate_job_id"),
                "baseline_evaluation_job_case_id": pair.get("baseline_job_case_id"),
                "candidate_evaluation_job_case_id": pair.get("candidate_job_case_id"),
                "baseline_score": baseline_eval.score if baseline_eval else None,
                "candidate_score": candidate_eval.score if candidate_eval else None,
                "baseline_status": baseline_eval.status if baseline_eval else None,
                "candidate_status": candidate_eval.status if candidate_eval else None,
                "classification": classification.upper()
                if classification != "not_comparable"
                else "NOT_COMPARABLE",
                "explanation": explanation,
                "failure_analysis": analyze_pair(
                    baseline=baseline_eval,
                    candidate=candidate_eval,
                )
                if classification == "regressed"
                else None,
            }
        )
    return buckets


async def decide_release(
    session: AsyncSession,
    *,
    baseline_version_id: UUID,
    candidate_version_id: UUID,
    minimum_pass_rate: Decimal,
    maximum_regressions: int,
    allowed_score_drop: Decimal,
    minimum_evaluation_coverage: Decimal = Decimal("1.0000"),
    required_evaluator_names: list[str] | None = None,
    workspace_id: UUID | None = None,
) -> ReleaseDecision:
    comparison = await compare_versions(
        session,
        baseline_version_id=baseline_version_id,
        candidate_version_id=candidate_version_id,
        workspace_id=workspace_id,
    )
    paired = await paired_case_comparison(
        session,
        baseline_version_id=baseline_version_id,
        candidate_version_id=candidate_version_id,
        workspace_id=workspace_id,
    )

    reasons: list[str] = []
    candidate_pass_rate = comparison.candidate.pass_rate
    if candidate_pass_rate is None:
        reasons.append("Candidate has no evaluation results yet.")

    paired_regressions = len(paired["regressed"])
    comparable_count = len(paired["regressed"]) + len(paired["improved"]) + len(paired["unchanged"])
    total_count = comparable_count + len(paired["not_comparable"])
    comparison_coverage = (
        (Decimal(comparable_count) / Decimal(total_count)).quantize(Decimal("0.0001"))
        if total_count
        else Decimal("0.0000")
    )
    required_evaluator_names = required_evaluator_names or []
    paired_items = [
        item
        for bucket in ("regressed", "improved", "unchanged", "not_comparable")
        for item in paired[bucket]
    ]
    observed_evaluators = {str(item["evaluator_name"]) for item in paired_items}
    missing_required_evaluators = sorted(set(required_evaluator_names) - observed_evaluators)

    paired_score_deltas = [
        item["candidate_score"] - item["baseline_score"]
        for bucket in ("regressed", "improved", "unchanged")
        for item in paired[bucket]
        if item["candidate_score"] is not None and item["baseline_score"] is not None
    ]
    paired_average_score_delta = (
        (sum(paired_score_deltas, Decimal("0.0000")) / Decimal(len(paired_score_deltas))).quantize(
            Decimal("0.0001")
        )
        if paired_score_deltas
        else None
    )

    if comparable_count == 0:
        reasons.append(
            "No behavioral test cases have evaluation evidence for both baseline and candidate."
        )

    if paired["not_comparable"]:
        reasons.append(
            f"{len(paired['not_comparable'])} test-case evaluations are missing "
            "baseline or candidate evidence."
        )

    coverage_blocked = comparison_coverage < minimum_evaluation_coverage
    if coverage_blocked:
        reasons.append(
            f"Comparison coverage {comparison_coverage} is below required "
            f"{minimum_evaluation_coverage}."
        )

    if missing_required_evaluators:
        reasons.append(
            "Required evaluator evidence is missing: "
            + ", ".join(missing_required_evaluators)
            + "."
        )

    runtime_evaluator_names = {"builtin.runtime_success", "builtin.trace_status"}
    runtime_failures = [
        item
        for item in paired_items
        if item["evaluator_name"] in runtime_evaluator_names
        and item["candidate_status"] == EvaluationStatus.FAIL
    ]
    runtime_blocked = bool(runtime_failures)
    if runtime_blocked:
        reasons.append(
            f"Candidate has {len(runtime_failures)} runtime-success check(s) that failed."
        )

    regressed_case_ids = {
        item["dataset_case_id"]
        for item in paired["regressed"]
        if item["dataset_case_id"] is not None
    }
    critical_regression_count = 0
    if regressed_case_ids:
        critical_cases = list(
            (
                await session.execute(
                    select(DatasetCase).where(DatasetCase.id.in_(regressed_case_ids))
                )
            ).scalars()
        )
        critical_regression_count = sum(
            1 for case in critical_cases if bool(case.meta.get("critical"))
        )
    critical_blocked = critical_regression_count > 0
    if critical_blocked:
        reasons.append(f"Candidate regressed {critical_regression_count} critical test case(s).")

    pass_rate_blocked = False
    if (
        candidate_pass_rate is not None
        and comparable_count > 0
        and candidate_pass_rate < minimum_pass_rate
    ):
        pass_rate_blocked = True
        reasons.append(
            f"Candidate pass rate {candidate_pass_rate} is below required {minimum_pass_rate}."
        )

    regression_blocked = paired_regressions > maximum_regressions
    if regression_blocked:
        reasons.append(
            f"Candidate introduced {paired_regressions} paired regressions; maximum allowed is "
            f"{maximum_regressions}."
        )

    score_drop_blocked = False
    if paired_average_score_delta is None:
        reasons.append("Paired score delta is unavailable.")
    elif paired_average_score_delta < -allowed_score_drop:
        score_drop_blocked = True
        reasons.append(
            "Candidate paired average score changed by "
            f"{paired_average_score_delta}, beyond allowed drop "
            f"{allowed_score_drop}."
        )

    has_missing_evidence = (
        comparable_count == 0
        or bool(paired["not_comparable"])
        or coverage_blocked
        or bool(missing_required_evaluators)
    )
    has_blocker = (
        regression_blocked
        or pass_rate_blocked
        or score_drop_blocked
        or runtime_blocked
        or critical_blocked
    )

    if not reasons:
        decision = "PASS"
        summary = "Candidate satisfies the configured release criteria."
    elif has_missing_evidence and not has_blocker:
        decision = "REVIEW"
        summary = "AgentGuard does not have enough paired evidence for an automatic ship decision."
    elif has_blocker:
        decision = "BLOCK"
        summary = "Candidate should not ship under the current release criteria."
    else:
        decision = "REVIEW"
        summary = "Candidate needs human review before release."

    return ReleaseDecision(
        project_id=comparison.project_id,
        baseline_version_id=baseline_version_id,
        candidate_version_id=candidate_version_id,
        decision=decision,
        summary=summary,
        reasons=reasons or ["No blocking issues detected."],
        comparison=comparison,
        minimum_pass_rate=minimum_pass_rate,
        maximum_regressions=maximum_regressions,
        allowed_score_drop=allowed_score_drop,
        minimum_evaluation_coverage=minimum_evaluation_coverage,
        required_evaluator_names=required_evaluator_names,
        comparison_coverage=comparison_coverage,
        runtime_failure_count=len(runtime_failures),
        critical_regression_count=critical_regression_count,
    )
