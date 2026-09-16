import uuid
from datetime import timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from agentguard_api.core.config import Settings
from agentguard_api.core.time import utc_now
from agentguard_api.models import (
    ApplicationVersion,
    Dataset,
    DatasetCase,
    EvaluationMethod,
    EvaluationStatus,
    Project,
)
from agentguard_api.models.enums import RunStatus, SpanType
from agentguard_api.schemas.dataset import DatasetCaseCreate, DatasetCreate, DatasetImport
from agentguard_api.schemas.evaluation import EvaluationCreate
from agentguard_api.schemas.trace import SpanIngest, TraceIngest
from agentguard_api.services.errors import ConflictError, NotFoundError, ValidationError
from agentguard_api.services.evaluations import create_evaluation
from agentguard_api.services.llm_judge import answer_quality_rubric, judge_answer_quality
from agentguard_api.services.trace_ingestion import ingest_trace

DEMO_DOCUMENTS = [
    {
        "id": "doc-agentguard",
        "title": "AgentGuard",
        "body": "AgentGuard captures traces for LLM, RAG, and agentic applications.",
    },
    {
        "id": "doc-phase-one",
        "title": "Phase 1",
        "body": (
            "Phase 1 focuses on projects, versions, whole-trace ingestion, "
            "and trace exploration."
        ),
    },
    {
        "id": "doc-replay",
        "title": "Counterfactual Replay",
        "body": "Counterfactual replay is a future flagship capability, not part of Phase 1.",
    },
]


def _retrieve(question: str) -> list[dict[str, str]]:
    terms = {term.strip("?.!,").lower() for term in question.split()}
    scored = []
    for document in DEMO_DOCUMENTS:
        text = f"{document['title']} {document['body']}".lower()
        score = sum(1 for term in terms if term and term in text)
        if score:
            scored.append((score, document))
    return [
        document for _, document in sorted(scored, key=lambda item: item[0], reverse=True)
    ] or DEMO_DOCUMENTS[:1]


def _generate_answer(question: str, documents: list[dict[str, str]]) -> str:
    if "fail" in question.lower():
        raise RuntimeError("deterministic demo generation failure requested")
    context = " ".join(document["body"] for document in documents)
    return f"Based on the local demo corpus: {context}"


async def create_dataset(
    session: AsyncSession,
    payload: DatasetCreate,
    *,
    workspace_id: UUID | None = None,
) -> Dataset:
    stmt = select(Project).where(Project.id == payload.project_id)
    if workspace_id is not None:
        stmt = stmt.where(Project.workspace_id == workspace_id)
    project = await session.scalar(stmt)
    if project is None:
        raise NotFoundError(
            "project was not found",
            metadata={"project_id": str(payload.project_id)},
        )

    dataset = Dataset(
        project_id=project.id,
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        meta=payload.metadata,
    )
    session.add(dataset)
    await session.flush()
    for case_payload in payload.cases:
        session.add(_case_from_payload(dataset.id, case_payload))
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError(
            "dataset slug or case name already exists for this project/dataset",
            metadata={"project_id": str(payload.project_id), "slug": payload.slug},
        ) from exc
    return await get_dataset(session, dataset.id, workspace_id=workspace_id)


async def import_dataset(
    session: AsyncSession,
    payload: DatasetImport,
    *,
    workspace_id: UUID | None = None,
) -> Dataset:
    return await create_dataset(
        session,
        DatasetCreate(
            project_id=payload.project_id,
            name=payload.name,
            slug=payload.slug,
            description=payload.description,
            metadata=payload.metadata,
            cases=payload.cases,
        ),
        workspace_id=workspace_id,
    )


def _case_from_payload(dataset_id: UUID, payload: DatasetCaseCreate) -> DatasetCase:
    return DatasetCase(
        dataset_id=dataset_id,
        name=payload.name,
        input=payload.input,
        expected_output=payload.expected_output,
        expected_substring=payload.expected_substring,
        meta=payload.metadata,
    )


async def create_dataset_case(
    session: AsyncSession,
    dataset_id: UUID,
    payload: DatasetCaseCreate,
    *,
    workspace_id: UUID | None = None,
) -> DatasetCase:
    stmt = select(Dataset).join(Project).where(Dataset.id == dataset_id)
    if workspace_id is not None:
        stmt = stmt.where(Project.workspace_id == workspace_id)
    dataset = await session.scalar(stmt)
    if dataset is None:
        raise NotFoundError("dataset was not found", metadata={"dataset_id": str(dataset_id)})
    case = _case_from_payload(dataset.id, payload)
    session.add(case)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError(
            "dataset case name already exists for this dataset",
            metadata={"dataset_id": str(dataset_id), "name": payload.name},
        ) from exc
    await session.refresh(case)
    return case


async def get_dataset(
    session: AsyncSession,
    dataset_id: UUID,
    *,
    workspace_id: UUID | None = None,
) -> Dataset:
    stmt = (
        select(Dataset)
        .options(selectinload(Dataset.cases))
        .join(Project)
        .where(Dataset.id == dataset_id)
    )
    if workspace_id is not None:
        stmt = stmt.where(Project.workspace_id == workspace_id)
    result = await session.execute(
        stmt
    )
    dataset = result.scalar_one_or_none()
    if dataset is None:
        raise NotFoundError("dataset was not found", metadata={"dataset_id": str(dataset_id)})
    dataset.cases.sort(key=lambda case: case.created_at)
    return dataset


def dataset_list_query(
    project_id: UUID | None = None,
    workspace_id: UUID | None = None,
) -> Select:
    stmt = select(Dataset).options(selectinload(Dataset.cases)).join(Project)
    if project_id:
        stmt = stmt.where(Dataset.project_id == project_id)
    if workspace_id is not None:
        stmt = stmt.where(Project.workspace_id == workspace_id)
    return stmt.order_by(Dataset.created_at.desc())


async def list_datasets(
    session: AsyncSession,
    *,
    project_id: UUID | None,
    workspace_id: UUID | None = None,
    limit: int,
    offset: int,
) -> tuple[list[Dataset], int]:
    base = dataset_list_query(project_id, workspace_id)
    total = await session.scalar(select(func.count()).select_from(base.subquery()))
    result = await session.execute(base.limit(limit).offset(offset))
    datasets = list(result.scalars().unique())
    for dataset in datasets:
        dataset.cases.sort(key=lambda case: case.created_at)
    return datasets, int(total or 0)


async def run_dataset_case(
    session: AsyncSession,
    *,
    case_id: UUID,
    application_version_id: UUID,
    evaluator_name: str,
    settings: Settings,
    workspace_id: UUID | None = None,
):
    query = (
        select(DatasetCase)
        .options(selectinload(DatasetCase.dataset).selectinload(Dataset.project))
        .where(DatasetCase.id == case_id)
    )
    if workspace_id is not None:
        query = query.join(Dataset, Dataset.id == DatasetCase.dataset_id).join(Project).where(
            Project.workspace_id == workspace_id
        )
    result = await session.execute(query)
    case = result.scalar_one_or_none()
    if case is None:
        raise NotFoundError("dataset case was not found", metadata={"case_id": str(case_id)})

    version_query = (
        select(ApplicationVersion)
        .join(Project)
        .where(ApplicationVersion.id == application_version_id)
    )
    if workspace_id is not None:
        version_query = version_query.where(Project.workspace_id == workspace_id)
    version = await session.scalar(version_query)
    if version is None:
        raise NotFoundError(
            "application version was not found",
            metadata={"application_version_id": str(application_version_id)},
        )
    if version.project_id != case.dataset.project_id:
        raise ValidationError(
            "dataset case and application version must belong to the same project"
        )

    question = str(case.input.get("question", ""))
    if not question:
        raise ValidationError("dataset case input must include a non-empty question")

    started_at = utc_now()
    documents = _retrieve(question)
    answer: str | None = None
    run_error = None
    try:
        answer = _generate_answer(question, documents)
    except RuntimeError as exc:
        run_error = {
            "type": type(exc).__name__,
            "message": str(exc),
            "stacktrace": None,
            "code": "DEMO_GENERATION_FAILURE",
            "metadata": {"dataset_case_id": str(case.id)},
        }

    plan_start = started_at
    retrieve_start = started_at + timedelta(milliseconds=5)
    summarize_start = started_at + timedelta(milliseconds=10)
    generate_start = started_at + timedelta(milliseconds=15)
    ended_at = started_at + timedelta(milliseconds=30)
    trace_payload = TraceIngest(
        project_slug=case.dataset.project.slug,
        version=version.version,
        external_trace_id=f"dataset-run-{case.id}-{application_version_id}-{uuid.uuid4()}",
        name=f"dataset:{case.dataset.slug}/{case.name}",
        status=RunStatus.ERROR if run_error else RunStatus.OK,
        input={"question": question, "dataset_case_id": str(case.id)},
        output={"answer": answer} if answer is not None else None,
        metadata={
            "source": "dataset_run",
            "dataset_id": str(case.dataset_id),
            "dataset_case_id": str(case.id),
        },
        started_at=started_at,
        ended_at=ended_at,
        total_input_tokens=72,
        total_output_tokens=24 if answer else 0,
        error=run_error,
        spans=[
            SpanIngest(
                external_span_id="plan",
                type=SpanType.LLM,
                name="plan",
                status=RunStatus.OK,
                input={"question": question},
                output={
                    "steps": [
                        "retrieve local documents",
                        "summarize context",
                        "generate answer",
                    ]
                },
                provider="local",
                model_name="deterministic-planner",
                input_tokens=8,
                output_tokens=12,
                started_at=plan_start,
                ended_at=plan_start + timedelta(milliseconds=4),
            ),
            SpanIngest(
                external_span_id="retrieve",
                type=SpanType.RETRIEVER,
                name="retrieve",
                status=RunStatus.OK,
                input={"query": question},
                output={"documents": documents},
                started_at=retrieve_start,
                ended_at=retrieve_start + timedelta(milliseconds=8),
            ),
            SpanIngest(
                external_span_id="summarize-documents",
                parent_external_span_id="retrieve",
                type=SpanType.TOOL,
                name="summarize-documents",
                status=RunStatus.OK,
                input={"document_ids": [document["id"] for document in documents]},
                output={
                    "document_count": len(documents),
                    "character_count": sum(len(document["body"]) for document in documents),
                },
                started_at=summarize_start,
                ended_at=summarize_start + timedelta(milliseconds=3),
            ),
            SpanIngest(
                external_span_id="generate",
                type=SpanType.LLM,
                name="generate",
                status=RunStatus.ERROR if run_error else RunStatus.OK,
                input={"question": question, "documents": documents},
                output={"answer": answer} if answer is not None else None,
                provider="local",
                model_name="deterministic-generator",
                input_tokens=64,
                output_tokens=24 if answer else 0,
                started_at=generate_start,
                ended_at=generate_start + timedelta(milliseconds=12),
                error=run_error,
            ),
        ],
    )
    trace = await ingest_trace(session, trace_payload, settings, workspace_id=workspace_id)

    expected = case.expected_substring or ""
    score = Decimal("0.0000")
    label = "Evaluator did not pass"
    metadata = {
        "expected_substring": expected,
        "expected_output": case.expected_output,
        "answer": answer,
        "trace_status": trace.status.value,
    }
    if evaluator_name == "builtin.answer_contains":
        passed = bool(answer and expected.lower() in answer.lower())
        score = Decimal("1.0000") if passed else Decimal("0.0000")
        label = "Expected answer substring found" if passed else "Expected answer substring missing"
    elif evaluator_name == "builtin.answer_exact":
        expected_answer = str(
            case.expected_output if case.expected_output is not None else expected
        )
        passed = bool(answer and answer.strip() == expected_answer.strip())
        score = Decimal("1.0000") if passed else Decimal("0.0000")
        label = "Answer exactly matched" if passed else "Answer did not exactly match"
        metadata["expected_answer"] = expected_answer
    elif evaluator_name == "builtin.keyword_coverage":
        keywords = [part.strip().lower() for part in expected.split(",") if part.strip()]
        matched = [keyword for keyword in keywords if answer and keyword in answer.lower()]
        score = (
            (Decimal(len(matched)) / Decimal(len(keywords))).quantize(Decimal("0.0001"))
            if keywords
            else Decimal("0.0000")
        )
        passed = score >= Decimal("0.8000")
        label = "Keyword coverage passed" if passed else "Keyword coverage below threshold"
        metadata["matched_keywords"] = matched
        metadata["keywords"] = keywords
    elif evaluator_name == "builtin.llm_judge.answer_quality":
        verdict = judge_answer_quality(
            settings=settings,
            question=question,
            answer=answer,
            expected=expected,
            evidence=documents,
        )
        score = verdict.score.quantize(Decimal("0.0001"))
        passed = verdict.passed
        label = "LLM judge passed answer quality" if passed else "LLM judge found answer risk"
        metadata["judge_evidence"] = verdict.evidence
        metadata["judge_explanation"] = verdict.explanation
    else:
        raise ValidationError(
            "unsupported evaluator for dataset run",
            metadata={
                "supported": [
                    "builtin.answer_contains",
                    "builtin.answer_exact",
                    "builtin.keyword_coverage",
                    "builtin.llm_judge.answer_quality",
                ]
            },
        )
    evaluation = await create_evaluation(
        session,
        EvaluationCreate(
            trace_id=trace.id,
            dataset_id=case.dataset_id,
            dataset_case_id=case.id,
            evaluator_name=evaluator_name,
            evaluator_version="1.0.0",
            method=(
                EvaluationMethod.LLM_JUDGE
                if evaluator_name == "builtin.llm_judge.answer_quality"
                else EvaluationMethod.DETERMINISTIC_BEHAVIORAL
            ),
            rubric=(
                answer_quality_rubric()
                if evaluator_name == "builtin.llm_judge.answer_quality"
                else {"expected_substring": expected}
            ),
            judge_model=(
                settings.judge_model
                if evaluator_name == "builtin.llm_judge.answer_quality"
                else None
            ),
            score=score,
            threshold=(
                Decimal("1.0000")
                if evaluator_name != "builtin.keyword_coverage"
                else Decimal("0.8000")
            ),
            status=EvaluationStatus.PASS if passed else EvaluationStatus.FAIL,
            passed=passed,
            label=label,
            explanation=(
                "Built-in evaluator executed against the generated answer for this dataset case."
            ),
            metadata=metadata,
        ),
        workspace_id=workspace_id,
    )
    return trace, evaluation
