import json
from decimal import Decimal
from typing import Any
from urllib import error, request

from pydantic import BaseModel, Field
from pydantic import ValidationError as PydanticValidationError

from agentguard_api.core.config import Settings
from agentguard_api.services.errors import ValidationError

RUBRIC_VERSION = "answer-quality-v1"


class JudgeVerdict(BaseModel):
    score: Decimal = Field(ge=0, le=1)
    passed: bool
    explanation: str = Field(min_length=1, max_length=1200)
    evidence: list[str] = Field(default_factory=list)


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


def judge_answer_quality(
    *,
    settings: Settings,
    question: str,
    answer: str | None,
    expected: str,
    evidence: Any,
) -> JudgeVerdict:
    if not settings.judge_api_key:
        raise ValidationError(
            "AGENTGUARD_JUDGE_API_KEY is required for builtin.llm_judge.answer_quality"
        )
    messages = [
        {
            "role": "system",
            "content": (
                "You are an evaluator for AI application regression tests. Return only valid JSON "
                "with keys score, passed, explanation, and evidence. Do not treat yourself as "
                "ground truth; evaluate against the supplied rubric and expected requirement."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "rubric": answer_quality_rubric(),
                    "question": question,
                    "answer": answer,
                    "expected_requirement": expected,
                    "evidence": evidence,
                    "output_schema": {
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
    req = request.Request(
        f"{settings.judge_base_url.rstrip('/')}/chat/completions",
        data=body,
        headers={
            "authorization": f"Bearer {settings.judge_api_key}",
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=settings.judge_timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        raise ValidationError(
            "LLM judge provider request failed",
            metadata={"status_code": exc.code},
        ) from exc
    except OSError as exc:
        raise ValidationError(
            "LLM judge provider was unreachable",
            metadata={"error": str(exc)},
        ) from exc

    content = payload["choices"][0]["message"]["content"]
    try:
        return JudgeVerdict.model_validate_json(content)
    except (PydanticValidationError, ValueError) as exc:
        raise ValidationError("LLM judge returned invalid structured output") from exc
