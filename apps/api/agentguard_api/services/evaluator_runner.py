import json
from decimal import Decimal
from typing import Any
from uuid import UUID

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
    answer_quality_rubric,
    judge_answer_quality,
)


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
            documents.extend(
                document
                for document in value
                if isinstance(document, dict)
            )

    return documents


def _called_tools(trace: Trace) -> list[str]:
    return [
        span.name
        for span in trace.spans
        if span.type == SpanType.TOOL
    ]


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

    score = Decimal("0.0000")
    threshold = Decimal("1.0000")
    passed = False

    method = EvaluationMethod.DETERMINISTIC_BEHAVIORAL
    rubric: dict[str, Any] = {}
    judge_model: str | None = None
    label = "Evaluation failed"
    explanation = ""

    metadata: dict[str, Any] = {
        "answer": answer,
        "trace_status": trace.status.value,
    }

    if evaluator_name == "builtin.answer_contains":
        if not expected:
            raise ValidationError(
                "answer_contains requires expected_substring or expected_output"
            )

        passed = bool(
            answer
            and expected.lower() in answer.lower()
        )

        score = Decimal("1.0000") if passed else Decimal("0.0000")

        rubric = {
            "requirement": expected,
            "rule": "case-insensitive substring match",
        }

        label = (
            "Expected answer content found"
            if passed
            else "Expected answer content missing"
        )

        explanation = (
            "Checks whether the generated answer contains the required content."
        )

    elif evaluator_name == "builtin.answer_exact":
        if not expected:
            raise ValidationError(
                "answer_exact requires expected output"
            )

        passed = bool(
            answer
            and answer.strip() == expected.strip()
        )

        score = Decimal("1.0000") if passed else Decimal("0.0000")

        rubric = {
            "expected_answer": expected,
            "rule": "exact normalized string equality",
        }

        label = (
            "Answer exactly matched"
            if passed
            else "Answer did not exactly match"
        )

        explanation = "Checks exact answer equality."

    elif evaluator_name == "builtin.keyword_coverage":
        keywords = [
            part.strip().lower()
            for part in expected.split(",")
            if part.strip()
        ]

        if not keywords:
            raise ValidationError(
                "keyword_coverage requires comma-separated expected keywords"
            )

        matched = [
            keyword
            for keyword in keywords
            if answer and keyword in answer.lower()
        ]

        score = (
            Decimal(len(matched))
            / Decimal(len(keywords))
        ).quantize(Decimal("0.0001"))

        threshold = Decimal("0.8000")
        passed = score >= threshold

        rubric = {
            "keywords": keywords,
            "threshold": str(threshold),
        }

        metadata["matched_keywords"] = matched

        label = (
            "Keyword coverage passed"
            if passed
            else "Keyword coverage below threshold"
        )

        explanation = (
            "Measures how many required concepts appear explicitly in the answer."
        )

    elif evaluator_name == "builtin.llm_judge.answer_quality":
        if not expected:
            raise ValidationError(
                "LLM answer-quality evaluation requires an expected requirement"
            )

        verdict = judge_answer_quality(
            settings=settings,
            question=str(case.input.get("question", "")),
            answer=answer,
            expected=expected,
            evidence=documents,
        )

        score = verdict.score.quantize(Decimal("0.0001"))

        # IMPORTANT:
        # this was previously stored as 1.0 even though the rubric says 0.8.
        threshold = Decimal("0.8000")
        passed = verdict.passed

        method = EvaluationMethod.LLM_JUDGE
        rubric = answer_quality_rubric()
        judge_model = settings.judge_model

        label = (
            "Semantic answer quality passed"
            if passed
            else "Semantic answer quality regressed"
        )

        explanation = verdict.explanation

        metadata["judge_evidence"] = verdict.evidence

    elif evaluator_name == "builtin.retrieval.required_documents":
        expected_ids = {
            str(value)
            for value in case.meta.get("expected_document_ids", [])
        }

        if not expected_ids:
            raise ValidationError(
                "retrieval evaluator requires metadata.expected_document_ids"
            )

        actual_ids = {
            str(document.get("id"))
            for document in documents
            if document.get("id") is not None
        }

        matched = expected_ids & actual_ids

        score = (
            Decimal(len(matched))
            / Decimal(len(expected_ids))
        ).quantize(Decimal("0.0001"))

        threshold = Decimal("1.0000")
        passed = score >= threshold

        method = EvaluationMethod.RETRIEVAL

        rubric = {
            "expected_document_ids": sorted(expected_ids),
            "rule": "all required documents must be retrieved",
        }

        metadata["retrieved_document_ids"] = sorted(actual_ids)

        label = (
            "Required evidence retrieved"
            if passed
            else "Required evidence missing"
        )

        explanation = (
            "Checks whether retrieval returned every document required by this test case."
        )

    elif evaluator_name == "builtin.agent.expected_tool":
        expected_tools = {
            str(value)
            for value in case.meta.get("expected_tools", [])
        }

        if not expected_tools:
            raise ValidationError(
                "expected-tool evaluator requires metadata.expected_tools"
            )

        actual_tools = set(tools)
        matched = expected_tools & actual_tools

        score = (
            Decimal(len(matched))
            / Decimal(len(expected_tools))
        ).quantize(Decimal("0.0001"))

        passed = score >= Decimal("1.0000")

        rubric = {
            "expected_tools": sorted(expected_tools),
        }

        metadata["called_tools"] = tools

        label = (
            "Expected tool behavior observed"
            if passed
            else "Expected tool was not called"
        )

        explanation = (
            "Checks whether the agent executed the tools expected for this behavior."
        )

    elif evaluator_name == "builtin.agent.forbidden_tool":
        forbidden_tools = {
            str(value)
            for value in case.meta.get("forbidden_tools", [])
        }

        if not forbidden_tools:
            raise ValidationError(
                "forbidden-tool evaluator requires metadata.forbidden_tools"
            )

        actual_tools = set(tools)
        violations = forbidden_tools & actual_tools

        passed = not violations
        score = Decimal("1.0000") if passed else Decimal("0.0000")

        rubric = {
            "forbidden_tools": sorted(forbidden_tools),
        }

        metadata["called_tools"] = tools
        metadata["violations"] = sorted(violations)

        label = (
            "No forbidden tool used"
            if passed
            else "Forbidden tool used"
        )

        explanation = (
            "Checks whether the agent avoided actions that the test case explicitly forbids."
        )

    elif evaluator_name == "builtin.trace_status":
        method = EvaluationMethod.DETERMINISTIC_OPERATIONAL

        passed = trace.status.value == "OK"
        score = Decimal("1.0000") if passed else Decimal("0.0000")

        rubric = {
            "pass_condition": "trace.status == OK",
        }

        label = (
            "Run completed successfully"
            if passed
            else "Run failed"
        )

        explanation = (
            "Checks whether the complete AI application run finished without an error."
        )

    else:
        raise ValidationError(
            "unsupported evaluator",
            metadata={
                "evaluator_name": evaluator_name,
                "supported": [
                    "builtin.answer_contains",
                    "builtin.answer_exact",
                    "builtin.keyword_coverage",
                    "builtin.llm_judge.answer_quality",
                    "builtin.retrieval.required_documents",
                    "builtin.agent.expected_tool",
                    "builtin.agent.forbidden_tool",
                    "builtin.trace_status",
                ],
            },
        )

    return await create_evaluation(
        session,
        EvaluationCreate(
            trace_id=trace.id,
            dataset_id=case.dataset_id,
            dataset_case_id=case.id,
            evaluator_name=evaluator_name,
            evaluator_version="1.0.0",
            method=method,
            rubric=rubric,
            judge_model=judge_model,
            score=score,
            threshold=threshold,
            status=(
                EvaluationStatus.PASS
                if passed
                else EvaluationStatus.FAIL
            ),
            passed=passed,
            label=label,
            explanation=explanation,
            metadata=metadata,
        ),
        workspace_id=workspace_id,
    )