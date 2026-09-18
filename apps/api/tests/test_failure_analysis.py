from agentguard_api.services.failure_analysis import _stage_for_evaluator


def test_keyword_coverage_is_classified_as_generation_evidence():
    assert _stage_for_evaluator("builtin.keyword_coverage") == "generation"


def test_failure_stages_preserve_retrieval_tool_and_workflow_boundaries():
    assert _stage_for_evaluator("builtin.required_source") == "retrieval"
    assert _stage_for_evaluator("builtin.expected_tool") == "tool"
    assert _stage_for_evaluator("builtin.runtime_success") == "workflow"
