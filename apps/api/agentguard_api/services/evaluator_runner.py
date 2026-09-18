import json
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from uuid import UUID

from jsonschema import SchemaError, validate
from jsonschema import ValidationError as JsonSchemaValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agentguard_api.core.config import Settings
from agentguard_api.models import (
    DatasetCase,
    EvaluationMethod,
    EvaluationResult,
    EvaluationStatus,
    SpanType,
    Trace,
)
from agentguard_api.schemas.evaluation import EvaluationCreate
from agentguard_api.services.errors import ValidationError
from agentguard_api.services.evaluations import create_evaluation
from agentguard_api.services.llm_judge import (
    PROMPT_TEMPLATE_VERSION,
    answer_quality_rubric,
    groundedness_rubric,
    judge_answer_quality,
    judge_groundedness,
    judge_retrieval_relevance,
    judge_tool_selection,
    retrieval_relevance_rubric,
    tool_selection_rubric,
)


@dataclass
class EvaluationContext:
    trace: Trace
    case: DatasetCase
    settings: Settings
    answer: str | None
    documents: list[dict[str, Any]]
    tools: list[str]
    expected: str


@dataclass
class EvaluationOutcome:
    score: Decimal
    threshold: Decimal | None
    passed: bool
    method: EvaluationMethod
    rubric: dict[str, Any]
    label: str
    explanation: str
    metadata: dict[str, Any] = field(default_factory=dict)
    judge_model: str | None = None
    evaluator_version: str = "1.0.0"


class BuiltinEvaluator:
    name: str
    aliases: tuple[str, ...] = ()

    def evaluate(self, context: EvaluationContext) -> EvaluationOutcome:
        raise NotImplementedError


class EvaluatorRegistry:
    def __init__(self) -> None:
        self._evaluators: dict[str, BuiltinEvaluator] = {}

    def register(self, evaluator: BuiltinEvaluator) -> None:
        self._evaluators[evaluator.name] = evaluator
        for alias in evaluator.aliases:
            self._evaluators[alias] = evaluator

    def resolve(self, name: str) -> BuiltinEvaluator:
        try:
            return self._evaluators[name]
        except KeyError as exc:
            raise ValidationError(
                "unsupported evaluator",
                metadata={
                    "evaluator_name": name,
                    "supported": sorted(self._evaluators),
                },
            ) from exc

    def names(self) -> list[str]:
        return sorted(self._evaluators)


def evaluator_applies_to_case(evaluator_name: str, case: DatasetCase) -> bool:
    canonical_name = evaluator_registry.resolve(evaluator_name).name
    if canonical_name == "builtin.runtime_success":
        return True

    configured = case.meta.get("evaluators")
    if isinstance(configured, list) and configured:
        return evaluator_name in {str(name) for name in configured}

    expected = bool(
        case.expected_substring
        or case.expected_output is not None
        or case.meta.get("semantic_requirement")
    )
    applicability = {
        "builtin.required_content": expected,
        "builtin.exact_answer": expected,
        "builtin.keyword_coverage": bool(case.meta.get("required_keywords")) or expected,
        "builtin.structured_output": bool(
            case.meta.get("json_schema") or case.meta.get("expected_output_schema")
        ),
        "builtin.required_source": bool(
            case.meta.get("required_sources") or case.meta.get("expected_document_ids")
        ),
        "builtin.expected_tool": bool(
            case.meta.get("expected_tool") or case.meta.get("expected_tools")
        ),
        "builtin.forbidden_tool": bool(case.meta.get("forbidden_tools")),
        "builtin.runtime_success": True,
        "builtin.latency": bool(case.meta.get("latency_budget_ms")),
        "builtin.semantic_correctness": expected,
        "builtin.groundedness": True,
        "builtin.retrieval_relevance": True,
        "builtin.tool_selection": bool(
            case.meta.get("expected_tool")
            or case.meta.get("expected_tools")
            or case.meta.get("available_tools")
        ),
    }
    return applicability.get(canonical_name, True)


def _trace_answer(trace: Trace) -> str | None:
    output = trace.output

    if isinstance(output, str):
        return output

    if isinstance(output, dict):
        answer = output.get("answer")
        if answer is not None:
            return str(answer)

    return None


def _retrieved_documents(trace: Trace) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []

    for span in trace.spans:
        if span.type != SpanType.RETRIEVER:
            continue

        if not isinstance(span.output, dict):
            continue

        value = span.output.get("documents")

        if isinstance(value, list):
            documents.extend(document for document in value if isinstance(document, dict))

    return documents


def _called_tools(trace: Trace) -> list[str]:
    return [span.name for span in trace.spans if span.type == SpanType.TOOL]


def _expected_requirement(case: DatasetCase) -> str:
    if case.expected_substring:
        return case.expected_substring

    if case.expected_output is not None:
        if isinstance(case.expected_output, str):
            return case.expected_output

        return json.dumps(
            case.expected_output,
            sort_keys=True,
        )

    semantic_requirement = case.meta.get("semantic_requirement")

    return str(semantic_requirement or "")


class RequiredContentEvaluator(BuiltinEvaluator):
    name = "builtin.required_content"
    aliases = ("builtin.answer_contains", "required_content")

    def evaluate(self, context: EvaluationContext) -> EvaluationOutcome:
        if not context.expected:
            raise ValidationError("required_content requires an expected answer requirement")
        passed = bool(context.answer and context.expected.lower() in context.answer.lower())
        return EvaluationOutcome(
            score=Decimal("1.0000") if passed else Decimal("0.0000"),
            threshold=Decimal("1.0000"),
            passed=passed,
            method=EvaluationMethod.DETERMINISTIC_BEHAVIORAL,
            rubric={"requirement": context.expected, "rule": "case-insensitive substring match"},
            label="Expected answer content found" if passed else "Expected answer content missing",
            explanation="Checks whether the generated answer contains required content.",
            metadata={"expected": context.expected, "answer": context.answer},
        )


class ExactAnswerEvaluator(BuiltinEvaluator):
    name = "builtin.exact_answer"
    aliases = ("builtin.answer_exact", "exact_answer")

    def evaluate(self, context: EvaluationContext) -> EvaluationOutcome:
        if not context.expected:
            raise ValidationError("exact_answer requires an expected answer")
        passed = bool(context.answer and context.answer.strip() == context.expected.strip())
        return EvaluationOutcome(
            score=Decimal("1.0000") if passed else Decimal("0.0000"),
            threshold=Decimal("1.0000"),
            passed=passed,
            method=EvaluationMethod.DETERMINISTIC_BEHAVIORAL,
            rubric={
                "expected_answer": context.expected,
                "rule": "exact normalized string equality",
            },
            label="Answer exactly matched" if passed else "Answer did not exactly match",
            explanation="Checks exact answer equality.",
            metadata={"expected": context.expected, "answer": context.answer},
        )


class StructuredOutputEvaluator(BuiltinEvaluator):
    name = "builtin.structured_output"
    aliases = ("structured_output",)

    def evaluate(self, context: EvaluationContext) -> EvaluationOutcome:
        schema = context.case.meta.get("json_schema") or context.case.meta.get(
            "expected_output_schema"
        )
        if not isinstance(schema, dict):
            raise ValidationError(
                "structured_output requires metadata.json_schema or expectations.json_schema"
            )

        raw_output: Any = context.trace.output
        if isinstance(raw_output, dict) and "answer" in raw_output:
            raw_output = raw_output["answer"]
        parsed_output = raw_output
        parse_error: str | None = None
        if isinstance(raw_output, str):
            try:
                parsed_output = json.loads(raw_output)
            except json.JSONDecodeError as exc:
                parse_error = str(exc)

        passed = False
        validation_error: str | None = parse_error
        if parse_error is None:
            try:
                validate(instance=parsed_output, schema=schema)
                passed = True
            except JsonSchemaValidationError as exc:
                validation_error = exc.message
            except SchemaError as exc:
                raise ValidationError(
                    "structured_output received an invalid JSON Schema",
                    metadata={"schema_error": exc.message},
                ) from exc

        return EvaluationOutcome(
            score=Decimal("1.0000") if passed else Decimal("0.0000"),
            threshold=Decimal("1.0000"),
            passed=passed,
            method=EvaluationMethod.DETERMINISTIC_BEHAVIORAL,
            rubric={"json_schema": schema, "rule": "valid JSON matching the configured schema"},
            label="Structured output matched schema"
            if passed
            else "Structured output failed schema",
            explanation=(
                "The output is valid JSON and matches the configured schema."
                if passed
                else "The output did not satisfy the configured JSON schema."
            ),
            metadata={
                "validation_error": validation_error,
                "observed_output": parsed_output,
            },
        )


class KeywordCoverageEvaluator(BuiltinEvaluator):
    name = "builtin.keyword_coverage"
    aliases = ("keyword_coverage",)

    def evaluate(self, context: EvaluationContext) -> EvaluationOutcome:
        keywords = [part.strip().lower() for part in context.expected.split(",") if part.strip()]
        if not keywords:
            raise ValidationError("keyword_coverage requires comma-separated expected keywords")
        matched = [
            keyword for keyword in keywords if context.answer and keyword in context.answer.lower()
        ]
        score = (Decimal(len(matched)) / Decimal(len(keywords))).quantize(Decimal("0.0001"))
        threshold = Decimal("0.8000")
        passed = score >= threshold
        return EvaluationOutcome(
            score=score,
            threshold=threshold,
            passed=passed,
            method=EvaluationMethod.DETERMINISTIC_BEHAVIORAL,
            rubric={"keywords": keywords, "threshold": str(threshold)},
            label="Keyword coverage passed" if passed else "Keyword coverage below threshold",
            explanation="Measures how many required concepts appear explicitly in the answer.",
            metadata={"matched_keywords": matched, "answer": context.answer},
        )


class RequiredSourceEvaluator(BuiltinEvaluator):
    name = "builtin.required_source"
    aliases = ("builtin.retrieval.required_documents", "required_source")

    def evaluate(self, context: EvaluationContext) -> EvaluationOutcome:
        expected_ids = {
            str(value)
            for value in (
                context.case.meta.get("required_sources")
                or context.case.meta.get("expected_document_ids")
                or []
            )
        }
        if not expected_ids:
            raise ValidationError("required_source requires metadata.required_sources")
        actual_ids = {
            str(document.get("id"))
            for document in context.documents
            if document.get("id") is not None
        }
        matched = expected_ids & actual_ids
        score = (Decimal(len(matched)) / Decimal(len(expected_ids))).quantize(Decimal("0.0001"))
        passed = score >= Decimal("1.0000")
        return EvaluationOutcome(
            score=score,
            threshold=Decimal("1.0000"),
            passed=passed,
            method=EvaluationMethod.RETRIEVAL,
            rubric={
                "expected_document_ids": sorted(expected_ids),
                "rule": "all required documents must be retrieved",
            },
            label="Required evidence retrieved" if passed else "Required evidence missing",
            explanation=(
                "Checks whether retrieval returned every document required by this test case."
            ),
            metadata={
                "retrieved_document_ids": sorted(actual_ids),
                "matched_document_ids": sorted(matched),
            },
        )


class ExpectedToolEvaluator(BuiltinEvaluator):
    name = "builtin.expected_tool"
    aliases = ("builtin.agent.expected_tool", "expected_tool")

    def evaluate(self, context: EvaluationContext) -> EvaluationOutcome:
        expected_tools = {
            str(value)
            for value in (
                context.case.meta.get("expected_tools")
                or (
                    [context.case.meta["expected_tool"]]
                    if context.case.meta.get("expected_tool")
                    else []
                )
            )
        }
        if not expected_tools:
            raise ValidationError(
                "expected_tool requires metadata.expected_tool or metadata.expected_tools"
            )
        actual_tools = set(context.tools)
        matched = expected_tools & actual_tools
        score = (Decimal(len(matched)) / Decimal(len(expected_tools))).quantize(Decimal("0.0001"))
        passed = score >= Decimal("1.0000")
        return EvaluationOutcome(
            score=score,
            threshold=Decimal("1.0000"),
            passed=passed,
            method=EvaluationMethod.DETERMINISTIC_BEHAVIORAL,
            rubric={"expected_tools": sorted(expected_tools)},
            label="Expected tool behavior observed" if passed else "Expected tool was not called",
            explanation="Checks whether the agent executed the tools expected for this behavior.",
            metadata={"called_tools": context.tools, "matched_tools": sorted(matched)},
        )


class ForbiddenToolEvaluator(BuiltinEvaluator):
    name = "builtin.forbidden_tool"
    aliases = ("builtin.agent.forbidden_tool", "forbidden_tool")

    def evaluate(self, context: EvaluationContext) -> EvaluationOutcome:
        forbidden_tools = {str(value) for value in context.case.meta.get("forbidden_tools", [])}
        if not forbidden_tools:
            raise ValidationError("forbidden_tool requires metadata.forbidden_tools")
        violations = forbidden_tools & set(context.tools)
        passed = not violations
        return EvaluationOutcome(
            score=Decimal("1.0000") if passed else Decimal("0.0000"),
            threshold=Decimal("1.0000"),
            passed=passed,
            method=EvaluationMethod.DETERMINISTIC_BEHAVIORAL,
            rubric={"forbidden_tools": sorted(forbidden_tools)},
            label="No forbidden tool used" if passed else "Forbidden tool used",
            explanation=(
                "Checks whether the agent avoided actions that the test case explicitly forbids."
            ),
            metadata={"called_tools": context.tools, "violations": sorted(violations)},
        )


class RuntimeSuccessEvaluator(BuiltinEvaluator):
    name = "builtin.runtime_success"
    aliases = ("builtin.trace_status", "runtime_success")

    def evaluate(self, context: EvaluationContext) -> EvaluationOutcome:
        passed = context.trace.status.value == "OK"
        return EvaluationOutcome(
            score=Decimal("1.0000") if passed else Decimal("0.0000"),
            threshold=Decimal("1.0000"),
            passed=passed,
            method=EvaluationMethod.DETERMINISTIC_OPERATIONAL,
            rubric={"pass_condition": "trace.status == OK"},
            label="Run completed successfully" if passed else "Run failed",
            explanation="Checks whether the complete AI application run finished without an error.",
            metadata={"trace_status": context.trace.status.value},
        )


class LatencyEvaluator(BuiltinEvaluator):
    name = "builtin.latency"
    aliases = ("latency",)

    def evaluate(self, context: EvaluationContext) -> EvaluationOutcome:
        budget_ms = context.case.meta.get("latency_budget_ms")
        if budget_ms is None:
            raise ValidationError("latency requires metadata.latency_budget_ms")
        budget = Decimal(str(budget_ms))
        duration = Decimal(context.trace.duration_ms)
        passed = duration <= budget
        score = Decimal("1.0000") if passed else (budget / duration).quantize(Decimal("0.0001"))
        return EvaluationOutcome(
            score=score,
            threshold=Decimal("1.0000"),
            passed=passed,
            method=EvaluationMethod.DETERMINISTIC_OPERATIONAL,
            rubric={"latency_budget_ms": str(budget)},
            label="Latency budget passed" if passed else "Latency budget exceeded",
            explanation="Checks whether the run completed within the configured latency budget.",
            metadata={"duration_ms": context.trace.duration_ms, "latency_budget_ms": budget_ms},
        )


class SemanticCorrectnessEvaluator(BuiltinEvaluator):
    name = "builtin.semantic_correctness"
    aliases = ("builtin.llm_judge.answer_quality", "semantic_correctness")

    def evaluate(self, context: EvaluationContext) -> EvaluationOutcome:
        if not context.expected:
            raise ValidationError("semantic_correctness requires an expected requirement")
        verdict = judge_answer_quality(
            settings=context.settings,
            question=str(context.case.input.get("question", "")),
            answer=context.answer,
            expected=context.expected,
            evidence=context.documents,
        )
        return EvaluationOutcome(
            score=verdict.score.quantize(Decimal("0.0001")),
            threshold=Decimal("0.8000"),
            passed=verdict.passed,
            method=EvaluationMethod.LLM_JUDGE,
            rubric=answer_quality_rubric(),
            judge_model=context.settings.judge_model,
            label="Semantic correctness passed"
            if verdict.passed
            else "Semantic correctness failed",
            explanation=verdict.explanation,
            metadata={
                "judge_evidence": verdict.evidence,
                "answer": context.answer,
                "judge_provider": context.settings.judge_provider,
                "prompt_template_version": PROMPT_TEMPLATE_VERSION,
                "rubric_version": answer_quality_rubric()["version"],
            },
        )


class GroundednessEvaluator(BuiltinEvaluator):
    name = "builtin.groundedness"
    aliases = ("groundedness",)

    def evaluate(self, context: EvaluationContext) -> EvaluationOutcome:
        verdict = judge_groundedness(
            settings=context.settings, answer=context.answer, evidence=context.documents
        )
        return EvaluationOutcome(
            score=verdict.score.quantize(Decimal("0.0001")),
            threshold=Decimal("0.8000"),
            passed=verdict.passed,
            method=EvaluationMethod.LLM_JUDGE,
            rubric=groundedness_rubric(),
            judge_model=context.settings.judge_model,
            label="Groundedness passed" if verdict.passed else "Groundedness failed",
            explanation=verdict.explanation,
            metadata={
                "judge_evidence": verdict.evidence,
                "retrieved_documents": context.documents,
                "judge_provider": context.settings.judge_provider,
                "prompt_template_version": PROMPT_TEMPLATE_VERSION,
                "rubric_version": groundedness_rubric()["version"],
            },
        )


class RetrievalRelevanceEvaluator(BuiltinEvaluator):
    name = "builtin.retrieval_relevance"
    aliases = ("retrieval_relevance",)

    def evaluate(self, context: EvaluationContext) -> EvaluationOutcome:
        expected_ids = [
            str(value)
            for value in (
                context.case.meta.get("required_sources")
                or context.case.meta.get("expected_document_ids")
                or []
            )
        ]
        verdict = judge_retrieval_relevance(
            settings=context.settings,
            question=str(context.case.input.get("question", "")),
            evidence=context.documents,
            expected_document_ids=expected_ids,
        )
        return EvaluationOutcome(
            score=verdict.score.quantize(Decimal("0.0001")),
            threshold=Decimal("0.8000"),
            passed=verdict.passed,
            method=EvaluationMethod.LLM_JUDGE,
            rubric=retrieval_relevance_rubric(),
            judge_model=context.settings.judge_model,
            label="Retrieval relevance passed" if verdict.passed else "Retrieval relevance failed",
            explanation=verdict.explanation,
            metadata={
                "judge_evidence": verdict.evidence,
                "retrieved_documents": context.documents,
                "judge_provider": context.settings.judge_provider,
                "prompt_template_version": PROMPT_TEMPLATE_VERSION,
                "rubric_version": retrieval_relevance_rubric()["version"],
            },
        )


class ToolSelectionEvaluator(BuiltinEvaluator):
    name = "builtin.tool_selection"
    aliases = ("tool_selection",)

    def evaluate(self, context: EvaluationContext) -> EvaluationOutcome:
        verdict = judge_tool_selection(
            settings=context.settings,
            question=str(context.case.input.get("question", "")),
            tools=context.tools,
            expected_tools=[
                str(value)
                for value in (
                    context.case.meta.get("expected_tools")
                    or (
                        [context.case.meta["expected_tool"]]
                        if context.case.meta.get("expected_tool")
                        else []
                    )
                )
            ],
            forbidden_tools=[str(value) for value in context.case.meta.get("forbidden_tools", [])],
        )
        return EvaluationOutcome(
            score=verdict.score.quantize(Decimal("0.0001")),
            threshold=Decimal("0.8000"),
            passed=verdict.passed,
            method=EvaluationMethod.LLM_JUDGE,
            rubric=tool_selection_rubric(),
            judge_model=context.settings.judge_model,
            label="Tool selection passed" if verdict.passed else "Tool selection failed",
            explanation=verdict.explanation,
            metadata={
                "judge_evidence": verdict.evidence,
                "called_tools": context.tools,
                "judge_provider": context.settings.judge_provider,
                "prompt_template_version": PROMPT_TEMPLATE_VERSION,
                "rubric_version": tool_selection_rubric()["version"],
            },
        )


evaluator_registry = EvaluatorRegistry()
for _evaluator in (
    RequiredContentEvaluator(),
    ExactAnswerEvaluator(),
    StructuredOutputEvaluator(),
    KeywordCoverageEvaluator(),
    RequiredSourceEvaluator(),
    ExpectedToolEvaluator(),
    ForbiddenToolEvaluator(),
    RuntimeSuccessEvaluator(),
    LatencyEvaluator(),
    SemanticCorrectnessEvaluator(),
    GroundednessEvaluator(),
    RetrievalRelevanceEvaluator(),
    ToolSelectionEvaluator(),
):
    evaluator_registry.register(_evaluator)


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


async def evaluate_trace_against_case(
    session: AsyncSession,
    *,
    trace: Trace,
    case: DatasetCase,
    evaluator_name: str,
    settings: Settings,
    workspace_id: UUID | None,
) -> EvaluationResult:

    existing = await _existing_evaluation(
        session,
        trace_id=trace.id,
        evaluator_name=evaluator_name,
    )

    if existing is not None:
        return existing

    answer = _trace_answer(trace)
    documents = _retrieved_documents(trace)
    tools = _called_tools(trace)

    expected = _expected_requirement(case)

    context = EvaluationContext(
        trace=trace,
        case=case,
        settings=settings,
        answer=answer,
        documents=documents,
        tools=tools,
        expected=expected,
    )
    evaluator = evaluator_registry.resolve(evaluator_name)
    outcome = evaluator.evaluate(context)
    metadata = {
        "answer": answer,
        "trace_status": trace.status.value,
        **outcome.metadata,
    }

    return await create_evaluation(
        session,
        EvaluationCreate(
            trace_id=trace.id,
            dataset_id=case.dataset_id,
            dataset_case_id=case.id,
            evaluator_name=evaluator_name,
            evaluator_version=outcome.evaluator_version,
            method=outcome.method,
            rubric=outcome.rubric,
            judge_model=outcome.judge_model,
            score=outcome.score,
            threshold=outcome.threshold,
            status=(EvaluationStatus.PASS if outcome.passed else EvaluationStatus.FAIL),
            passed=outcome.passed,
            label=outcome.label,
            explanation=outcome.explanation,
            metadata=metadata,
        ),
        workspace_id=workspace_id,
    )
