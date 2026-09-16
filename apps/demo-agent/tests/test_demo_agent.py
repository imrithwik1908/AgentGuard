from agentguard import AgentGuard

from demo_agent.agent import answer_question


def test_demo_agent_success(monkeypatch):
    captured = {}

    def fake_submit(_self, trace):
        captured["payload"] = trace.to_payload()

    monkeypatch.setattr(AgentGuard, "_submit_trace", fake_submit)
    monkeypatch.delenv("DEMO_AGENT_PROVIDER", raising=False)
    client = AgentGuard(base_url="http://agentguard.test", project="research-agent", version="v1")

    answer = answer_question(client, "What is AgentGuard?", dataset_case_id="case-1")

    assert "AgentGuard captures traces" in answer
    assert captured["payload"]["input"]["dataset_case_id"] == "case-1"
    assert [span["type"] for span in captured["payload"]["spans"]] == [
        "LLM",
        "RETRIEVER",
        "TOOL",
        "LLM",
    ]


def test_demo_agent_failure_is_captured(monkeypatch):
    captured = {}

    def fake_submit(_self, trace):
        captured["payload"] = trace.to_payload()

    monkeypatch.setattr(AgentGuard, "_submit_trace", fake_submit)
    client = AgentGuard(base_url="http://agentguard.test", project="research-agent", version="v1")

    try:
        answer_question(client, "please fail generation")
    except RuntimeError:
        pass

    payload = captured["payload"]
    assert payload["status"] == "ERROR"
    assert payload["spans"][-1]["name"] == "generate"
    assert payload["spans"][-1]["status"] == "ERROR"
