from urllib import error

import pytest

from agentguard import AgentGuard


def test_nested_spans_are_serialized_parent_before_child(monkeypatch):
    captured = {}

    def fake_submit(_self, trace):
        captured["payload"] = trace.to_payload()

    monkeypatch.setattr(AgentGuard, "_submit_trace", fake_submit)
    client = AgentGuard(base_url="http://agentguard.test", project="research-agent", version="v1")

    with client.trace("answer-question", input={"question": "What is AgentGuard?"}) as trace:
        with trace.span("retrieve", type="RETRIEVER") as parent:
            with trace.span("summarize", type="TOOL") as child:
                child.set_output({"ok": True})
            parent.set_output({"docs": []})
        trace.set_output({"answer": "AgentGuard captures traces."})

    spans = captured["payload"]["spans"]
    assert [span["name"] for span in spans] == ["retrieve", "summarize"]
    assert spans[1]["parent_external_span_id"] == spans[0]["external_span_id"]
    assert captured["payload"]["status"] == "OK"


def test_exception_capture_marks_trace_and_span_error(monkeypatch):
    captured = {}

    def fake_submit(_self, trace):
        captured["payload"] = trace.to_payload()

    monkeypatch.setattr(AgentGuard, "_submit_trace", fake_submit)
    client = AgentGuard(base_url="http://agentguard.test", project="research-agent", version="v1")

    with pytest.raises(RuntimeError):
        with client.trace("answer-question") as trace:
            with trace.span("generate", type="LLM"):
                raise RuntimeError("boom")

    payload = captured["payload"]
    assert payload["status"] == "ERROR"
    assert payload["error"]["type"] == "RuntimeError"
    assert payload["spans"][0]["status"] == "ERROR"
    assert payload["spans"][0]["error"]["message"] == "boom"


def test_submission_failure_warns_and_does_not_crash_by_default(monkeypatch, caplog):
    def fail_urlopen(*_args, **_kwargs):
        raise error.URLError("connection refused")

    monkeypatch.setattr("agentguard.client.request.urlopen", fail_urlopen)
    client = AgentGuard(base_url="http://agentguard.test", project="research-agent", version="v1")

    with client.trace("answer-question"):
        pass

    assert "agentguard_trace_submission_failed" in caplog.text


def test_submission_failure_can_raise(monkeypatch):
    def fail_urlopen(*_args, **_kwargs):
        raise error.URLError("connection refused")

    monkeypatch.setattr("agentguard.client.request.urlopen", fail_urlopen)
    client = AgentGuard(
        base_url="http://agentguard.test",
        project="research-agent",
        version="v1",
        raise_on_failure=True,
    )

    with pytest.raises(error.URLError):
        with client.trace("answer-question"):
            pass


def test_api_key_header_is_sent(monkeypatch):
    captured = {}

    class Response:
        status = 201

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def fake_urlopen(req, **_kwargs):
        captured["api_key"] = req.headers["X-agentguard-api-key"]
        return Response()

    monkeypatch.setattr("agentguard.client.request.urlopen", fake_urlopen)
    client = AgentGuard(
        base_url="http://agentguard.test",
        project="research-agent",
        version="v1",
        api_key="ag_test",
    )

    with client.trace("answer-question"):
        pass

    assert captured["api_key"] == "ag_test"
