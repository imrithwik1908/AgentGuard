from types import SimpleNamespace
from uuid import uuid4

from agentguard_api.models.enums import RunStatus
from agentguard_api.services.evaluations import orchestration_job_request_id
from agentguard_api.services.evaluator_runner import (
    EvaluationContext,
    evaluator_applies_to_case,
    evaluator_registry,
)


def _context(**overrides):
    case = SimpleNamespace(
        input={"question": "Can I return an opened laptop after 45 days?"},
        expected_substring="Opened electronics must be returned within 30 days.",
        expected_output=None,
        meta={
            "required_sources": ["opened-electronics-policy"],
            "expected_tool": "policy_lookup",
            "forbidden_tools": ["issue_refund"],
            "latency_budget_ms": 1000,
        },
    )
    trace = SimpleNamespace(status=RunStatus.OK, duration_ms=800)
    defaults = {
        "trace": trace,
        "case": case,
        "settings": SimpleNamespace(judge_model="test-judge"),
        "answer": "Opened electronics must be returned within 30 days.",
        "documents": [{"id": "opened-electronics-policy", "score": 0.91}],
        "tools": ["policy_lookup"],
        "expected": "Opened electronics must be returned within 30 days.",
    }
    defaults.update(overrides)
    return EvaluationContext(**defaults)


def test_registry_resolves_builtin_evaluators():
    assert evaluator_registry.resolve("builtin.required_content")
    assert evaluator_registry.resolve("builtin.answer_contains")
    assert evaluator_registry.resolve("builtin.required_source")
    assert evaluator_registry.resolve("builtin.expected_tool")
    assert evaluator_registry.resolve("builtin.forbidden_tool")
    assert evaluator_registry.resolve("builtin.structured_output")


def test_orchestration_job_request_ids_are_stable_and_database_safe():
    version_id = uuid4()
    first = orchestration_job_request_id(
        "dashboard:" + "x" * 110, version_id, "builtin.required_content"
    )
    second = orchestration_job_request_id(
        "dashboard:" + "x" * 110, version_id, "builtin.required_content"
    )

    assert first == second
    assert first is not None
    assert len(first) <= 120


def test_required_source_reads_retrieval_evidence():
    outcome = evaluator_registry.resolve("builtin.required_source").evaluate(_context())
    assert outcome.passed is True
    assert outcome.metadata["matched_document_ids"] == ["opened-electronics-policy"]


def test_expected_tool_reads_tool_spans():
    outcome = evaluator_registry.resolve("builtin.expected_tool").evaluate(_context())
    assert outcome.passed is True
    assert outcome.metadata["called_tools"] == ["policy_lookup"]


def test_evaluators_only_apply_to_cases_with_matching_expectations():
    case = _context().case
    assert evaluator_applies_to_case("builtin.required_content", case) is True
    assert evaluator_applies_to_case("builtin.required_source", case) is True
    assert evaluator_applies_to_case("builtin.expected_tool", case) is True

    case.meta = {}
    assert evaluator_applies_to_case("builtin.required_content", case) is True
    assert evaluator_applies_to_case("builtin.required_source", case) is False
    assert evaluator_applies_to_case("builtin.expected_tool", case) is False
    assert evaluator_applies_to_case("builtin.runtime_success", case) is True

    case.meta = {"evaluators": ["builtin.required_content"]}
    assert evaluator_applies_to_case("builtin.runtime_success", case) is True


def test_forbidden_tool_detects_violation():
    outcome = evaluator_registry.resolve("builtin.forbidden_tool").evaluate(
        _context(tools=["policy_lookup", "issue_refund"])
    )
    assert outcome.passed is False
    assert outcome.metadata["violations"] == ["issue_refund"]


def test_structured_output_validates_json_schema():
    context = _context()
    context.case.meta["json_schema"] = {
        "type": "object",
        "required": ["decision"],
        "properties": {"decision": {"type": "string", "enum": ["approve", "deny"]}},
        "additionalProperties": False,
    }
    context.trace.output = {"answer": '{"decision":"approve"}'}
    outcome = evaluator_registry.resolve("builtin.structured_output").evaluate(context)
    assert outcome.passed is True
    assert outcome.method.value == "DETERMINISTIC_BEHAVIORAL"


def test_structured_output_reports_schema_failure():
    context = _context()
    context.case.meta["json_schema"] = {
        "type": "object",
        "required": ["decision"],
        "properties": {"decision": {"type": "string"}},
    }
    context.trace.output = {"answer": '{"wrong":true}'}
    outcome = evaluator_registry.resolve("builtin.structured_output").evaluate(context)
    assert outcome.passed is False
    assert "required property" in str(outcome.metadata["validation_error"])
