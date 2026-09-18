from __future__ import annotations

from decimal import Decimal
from typing import Any

from agentguard_api.models import EvaluationResult


def analyze_pair(
    *,
    baseline: EvaluationResult | None,
    candidate: EvaluationResult | None,
) -> dict[str, Any] | None:
    if baseline is None or candidate is None:
        return None
    stage = _stage_for_evaluator(candidate.evaluator_name)
    evidence: list[str] = []
    if baseline.status != candidate.status:
        evidence.append(f"status changed from {baseline.status.value} to {candidate.status.value}")
    score_delta = candidate.score - baseline.score
    evidence.append(f"score movement {score_delta}")
    if candidate.explanation:
        evidence.append(candidate.explanation)

    summary = _summary(stage, score_delta)
    confidence = Decimal("0.6000")
    if stage != "unknown":
        confidence = Decimal("0.7500")
    return {
        "summary": summary,
        "likely_failure_stage": stage,
        "evidence": evidence,
        "confidence": str(confidence),
        "hypotheses": _hypotheses(stage),
        "causality": "correlated evidence only; no causal claim",
    }


def _stage_for_evaluator(evaluator_name: str) -> str:
    lowered = evaluator_name.lower()
    if "retrieval" in lowered or "source" in lowered or "grounded" in lowered:
        return "retrieval"
    if "tool" in lowered:
        return "tool"
    if "answer" in lowered or "semantic" in lowered or "content" in lowered:
        return "generation"
    if "runtime" in lowered or "trace" in lowered or "latency" in lowered:
        return "workflow"
    return "unknown"


def _summary(stage: str, score_delta: Decimal) -> str:
    direction = "lower" if score_delta < 0 else "different"
    if stage == "retrieval":
        return (
            "The first supported divergence appears in retrieval-related evidence "
            f"with a {direction} candidate score."
        )
    if stage == "tool":
        return (
            "The first supported divergence appears in tool/action evidence "
            f"with a {direction} candidate score."
        )
    if stage == "generation":
        return (
            "The first supported divergence appears in generated-answer evidence "
            f"with a {direction} candidate score."
        )
    if stage == "workflow":
        return (
            "The first supported divergence appears in execution/workflow evidence "
            f"with a {direction} candidate score."
        )
    return f"AgentGuard found a paired evaluation difference with a {direction} candidate score."


def _hypotheses(stage: str) -> list[str]:
    if stage == "retrieval":
        return [
            "The candidate may have retrieved different or weaker evidence.",
            "Additional retrieved context may have coincided with distractor evidence.",
        ]
    if stage == "tool":
        return ["The candidate may have selected a different action or missed an expected tool."]
    if stage == "generation":
        return ["The candidate answer no longer satisfies the expected behavior."]
    if stage == "workflow":
        return ["The candidate execution path may have changed operational behavior."]
    return ["Inspect baseline and candidate traces for the first divergent step."]
