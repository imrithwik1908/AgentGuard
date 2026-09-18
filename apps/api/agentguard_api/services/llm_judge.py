import json
from decimal import Decimal
from typing import Any
from urllib import error, request

from pydantic import BaseModel, Field, model_validator
from pydantic import ValidationError as PydanticValidationError

from agentguard_api.core.config import Settings
from agentguard_api.services.errors import JudgeUnavailableError, ValidationError

RUBRIC_VERSION = "answer-quality-v1"
PROMPT_TEMPLATE_VERSION = "structured-judge-v1"


class JudgeVerdict(BaseModel):
    score: Decimal = Field(ge=0, le=1)
    passed: bool
    explanation: str = Field(min_length=1, max_length=1200)
    evidence: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_pass_threshold(self) -> "JudgeVerdict":
        if self.passed != (self.score >= Decimal("0.8")):
            raise ValueError("passed must agree with the fixed 0.8 judge threshold")
        return self


class FailureAnalysisVerdict(BaseModel):
    summary: str = Field(min_length=1, max_length=1200)
    likely_failure_stage: str = Field(pattern=r"^(retrieval|generation|tool|workflow|unknown)$")
    evidence: list[str] = Field(default_factory=list)
    confidence: Decimal = Field(ge=0, le=1)
    hypotheses: list[str] = Field(default_factory=list)


def answer_quality_rubric() -> dict[str, Any]:
    return {
        "version": RUBRIC_VERSION,
        "criteria": [
            "The answer addresses the user's question.",
            "The answer is consistent with the expected requirement.",
            "The answer does not invent policy details that conflict with the supplied evidence.",
        ],
        "threshold": "0.8000",
    }


def groundedness_rubric() -> dict[str, Any]:
    return {
        "version": "groundedness-v1",
        "criteria": [
            "Material answer claims are supported by retrieved evidence.",
            "The answer does not add policy details absent from evidence.",
            "Unsupported claims lower the score even when the answer is fluent.",
        ],
        "threshold": "0.8000",
    }


def retrieval_relevance_rubric() -> dict[str, Any]:
    return {
        "version": "retrieval-relevance-v1",
        "criteria": [
            "Retrieved documents are relevant to the user request.",
            "Distractor documents reduce the score.",
            "Required policy evidence should be present when specified.",
        ],
        "threshold": "0.8000",
    }


def tool_selection_rubric() -> dict[str, Any]:
    return {
        "version": "tool-selection-v1",
        "criteria": [
            "The selected tool or action is appropriate for the user request.",
            "Expected tools should be used when specified.",
            "Forbidden tools should not be used.",
        ],
        "threshold": "0.8000",
    }


def _judge_structured[StructuredVerdict: BaseModel](
    *,
    settings: Settings,
    rubric: dict[str, Any],
    payload: dict[str, Any],
    missing_key_message: str,
    verdict_model: type[StructuredVerdict] = JudgeVerdict,
    output_schema: dict[str, str] | None = None,
) -> StructuredVerdict:
    if not settings.judge_enabled:
        raise JudgeUnavailableError(
            missing_key_message,
            metadata={"provider": settings.judge_provider},
        )
    messages = [
        {
            "role": "system",
            "content": (
                "You evaluate stored AI-application evidence against an explicit rubric. "
                "Return only valid JSON matching the requested schema. Never claim causality "
                "from correlation, and do not treat your judgment as ground truth."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "rubric": rubric,
                    **payload,
                    "output_schema": output_schema
                    or {
                        "score": "number between 0 and 1",
                        "passed": "boolean; true when score >= 0.8",
                        "explanation": "short evidence-backed explanation",
                        "evidence": "list of quoted or referenced facts used by the judge",
                    },
                }
            ),
        },
    ]
    body = json.dumps(
        {
            "model": settings.judge_model,
            "messages": messages,
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
    ).encode("utf-8")
    base_url = settings.judge_base_url.rstrip("/")
    if settings.judge_provider == "ollama" and not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"
    headers = {"content-type": "application/json"}
    if settings.judge_api_key:
        headers["authorization"] = f"Bearer {settings.judge_api_key}"
    req = request.Request(
        f"{base_url}/chat/completions",
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=settings.judge_timeout_seconds) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        raise JudgeUnavailableError(
            "LLM judge provider request failed",
            metadata={"provider": settings.judge_provider, "status_code": exc.code},
        ) from exc
    except (OSError, TimeoutError) as exc:
        raise JudgeUnavailableError(
            "LLM judge provider was unreachable",
            metadata={"provider": settings.judge_provider, "error": str(exc)},
        ) from exc

    try:
        content = response_payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValidationError("LLM judge returned an invalid provider response") from exc
    try:
        return verdict_model.model_validate_json(content)
    except (PydanticValidationError, ValueError) as exc:
        raise ValidationError("LLM judge returned invalid structured output") from exc


def judge_answer_quality(
    *,
    settings: Settings,
    question: str,
    answer: str | None,
    expected: str,
    evidence: Any,
) -> JudgeVerdict:
    return _judge_structured(
        settings=settings,
        rubric=answer_quality_rubric(),
        payload={
            "question": question,
            "answer": answer,
            "expected_requirement": expected,
            "evidence": evidence,
        },
        missing_key_message="AGENTGUARD_JUDGE_API_KEY is required for semantic correctness",
    )


def judge_groundedness(*, settings: Settings, answer: str | None, evidence: Any) -> JudgeVerdict:
    return _judge_structured(
        settings=settings,
        rubric=groundedness_rubric(),
        payload={"answer": answer, "retrieved_evidence": evidence},
        missing_key_message="AGENTGUARD_JUDGE_API_KEY is required for groundedness",
    )


def judge_retrieval_relevance(
    *,
    settings: Settings,
    question: str,
    evidence: Any,
    expected_document_ids: list[str],
) -> JudgeVerdict:
    return _judge_structured(
        settings=settings,
        rubric=retrieval_relevance_rubric(),
        payload={
            "question": question,
            "retrieved_evidence": evidence,
            "expected_document_ids": expected_document_ids,
        },
        missing_key_message="AGENTGUARD_JUDGE_API_KEY is required for retrieval relevance",
    )


def judge_tool_selection(
    *,
    settings: Settings,
    question: str,
    tools: list[str],
    expected_tools: list[str],
    forbidden_tools: list[str],
) -> JudgeVerdict:
    return _judge_structured(
        settings=settings,
        rubric=tool_selection_rubric(),
        payload={
            "question": question,
            "called_tools": tools,
            "expected_tools": expected_tools,
            "forbidden_tools": forbidden_tools,
        },
        missing_key_message="AGENTGUARD_JUDGE_API_KEY is required for tool selection",
    )


def judge_failure_analysis(
    *,
    settings: Settings,
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    evaluation_evidence: list[dict[str, Any]],
    configuration_changes: list[dict[str, Any]],
) -> FailureAnalysisVerdict:
    rubric = {
        "version": "failure-analysis-v1",
        "criteria": [
            "Identify the first supported divergence in stored evidence.",
            "Distinguish observation from hypothesis.",
            "Never claim a configuration change caused a regression.",
        ],
    }
    return _judge_structured(
        settings=settings,
        rubric=rubric,
        payload={
            "baseline": baseline,
            "candidate": candidate,
            "evaluation_evidence": evaluation_evidence,
            "configuration_changes": configuration_changes,
            "analysis_instruction": (
                "Identify the earliest supported divergence, separate observations from "
                "hypotheses, and avoid causal claims."
            ),
        },
        missing_key_message="An enabled judge provider is required for AI failure analysis",
        verdict_model=FailureAnalysisVerdict,
        output_schema={
            "summary": "concise evidence-backed summary without causal claims",
            "likely_failure_stage": "retrieval|generation|tool|workflow|unknown",
            "evidence": "list of concrete observations from supplied evidence",
            "confidence": "number between 0 and 1",
            "hypotheses": "list of explicitly uncertain possible explanations",
        },
    )
