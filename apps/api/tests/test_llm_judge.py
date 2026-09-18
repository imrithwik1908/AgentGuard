import json
from decimal import Decimal
from types import SimpleNamespace

import pytest

from agentguard_api.core.config import Settings
from agentguard_api.services.errors import JudgeUnavailableError, ValidationError
from agentguard_api.services.llm_judge import (
    judge_answer_quality,
    judge_failure_analysis,
    judge_groundedness,
    judge_retrieval_relevance,
    judge_tool_selection,
)


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_ollama_uses_openai_compatible_v1_without_api_key(monkeypatch):
    captured = {}

    def fake_urlopen(req, **_kwargs):
        captured["url"] = req.full_url
        captured["authorization"] = req.headers.get("Authorization")
        return _Response(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "score": 0.9,
                                    "passed": True,
                                    "explanation": "The answer satisfies the requirement.",
                                    "evidence": ["required policy statement"],
                                }
                            )
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("agentguard_api.services.llm_judge.request.urlopen", fake_urlopen)
    settings = Settings(
        judge_provider="ollama",
        judge_base_url="http://localhost:11434",
        judge_model="qwen2.5:0.5b",
    )
    verdict = judge_answer_quality(
        settings=settings,
        question="What is the return window?",
        answer="Opened electronics have a 30-day return window.",
        expected="30-day return window",
        evidence=[{"id": "returns", "text": "Opened electronics: 30 days."}],
    )
    assert verdict.passed is True
    assert captured["url"] == "http://localhost:11434/v1/chat/completions"
    assert captured["authorization"] is None


def test_disabled_judge_reports_unavailable_without_calling_provider(monkeypatch):
    called = SimpleNamespace(value=False)

    def fake_urlopen(*_args, **_kwargs):
        called.value = True
        raise AssertionError("provider should not be called")

    monkeypatch.setattr("agentguard_api.services.llm_judge.request.urlopen", fake_urlopen)
    settings = Settings(judge_provider="disabled")
    with pytest.raises(JudgeUnavailableError) as exc_info:
        judge_answer_quality(
            settings=settings,
            question="question",
            answer="answer",
            expected="expected",
            evidence=[],
        )
    assert exc_info.value.code == "judge_unavailable"
    assert called.value is False


def test_local_judge_supports_all_ai_evaluation_inputs(monkeypatch):
    requests = []

    def fake_urlopen(req, **_kwargs):
        requests.append(json.loads(req.data.decode("utf-8")))
        return _Response(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "score": 0.85,
                                    "passed": True,
                                    "explanation": "Stored evidence supports the rubric.",
                                    "evidence": ["policy document and tool trace"],
                                }
                            )
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("agentguard_api.services.llm_judge.request.urlopen", fake_urlopen)
    settings = Settings(
        judge_provider="ollama",
        judge_base_url="http://localhost:11434",
        judge_model="small-local-judge",
    )
    assert judge_groundedness(
        settings=settings, answer="answer", evidence=[{"id": "policy"}]
    ).passed
    assert judge_retrieval_relevance(
        settings=settings,
        question="question",
        evidence=[{"id": "policy"}],
        expected_document_ids=["policy"],
    ).passed
    assert judge_tool_selection(
        settings=settings,
        question="question",
        tools=["policy_lookup"],
        expected_tools=["policy_lookup"],
        forbidden_tools=[],
    ).passed
    assert len(requests) == 3
    assert all(request["temperature"] == 0 for request in requests)


def test_failure_analysis_uses_direct_validated_structure(monkeypatch):
    def fake_urlopen(_req, **_kwargs):
        return _Response(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "summary": (
                                        "The first observed difference is retrieval evidence."
                                    ),
                                    "likely_failure_stage": "retrieval",
                                    "evidence": ["candidate retrieved an additional distractor"],
                                    "confidence": 0.74,
                                    "hypotheses": [
                                        "The extra context may have influenced generation."
                                    ],
                                }
                            )
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("agentguard_api.services.llm_judge.request.urlopen", fake_urlopen)
    verdict = judge_failure_analysis(
        settings=Settings(
            judge_provider="ollama",
            judge_base_url="http://localhost:11434",
            judge_model="small-local-judge",
        ),
        baseline={"documents": ["policy"]},
        candidate={"documents": ["policy", "distractor"]},
        evaluation_evidence=[{"groundedness_delta": -0.2}],
        configuration_changes=[{"top_k": [4, 10]}],
    )
    assert verdict.likely_failure_stage == "retrieval"
    assert verdict.confidence == Decimal("0.74")
    assert "may" in verdict.hypotheses[0]


def test_judge_rejects_inconsistent_pass_flag(monkeypatch):
    def fake_urlopen(_req, **_kwargs):
        return _Response(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "score": 0.2,
                                    "passed": True,
                                    "explanation": "inconsistent",
                                    "evidence": [],
                                }
                            )
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("agentguard_api.services.llm_judge.request.urlopen", fake_urlopen)
    with pytest.raises(ValidationError, match="invalid structured output"):
        judge_answer_quality(
            settings=Settings(
                judge_provider="ollama",
                judge_base_url="http://localhost:11434",
                judge_model="small-local-judge",
            ),
            question="question",
            answer="answer",
            expected="expected",
            evidence=[],
        )
