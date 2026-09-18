import asyncio
from types import SimpleNamespace
from urllib import error

import pytest

from agentguard import AgentGuard
from agentguard.integrations.openai import instrument_openai


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


def test_trace_run_and_span_helpers_record_complete_run(monkeypatch):
    captured = {}

    def fake_submit(_self, trace):
        captured["payload"] = trace.to_payload()

    monkeypatch.setattr(AgentGuard, "_submit_trace", fake_submit)
    client = AgentGuard(base_url="http://agentguard.test", project="support-agent", version="v1")

    @client.trace_run("answer-question", input_arg="question")
    def answer(question: str):
        with client.retrieval("policy retrieval", query={"question": question}) as span:
            span.set_output({"documents": [{"id": "opened-electronics-policy", "score": 0.91}]})
        with client.tool(
            "policy_lookup", arguments={"policy_id": "opened-electronics-policy"}
        ) as span:
            span.set_output({"policy": "Opened electronics return within 30 days."})
        with client.llm_call("generate answer", provider="openai", model="gpt-test") as span:
            span.set_output({"answer": "Opened electronics must be returned within 30 days."})
            span.set_attributes(input_tokens=12, output_tokens=9)
        return {"answer": "Opened electronics must be returned within 30 days."}

    result = answer(question="Can I return an opened laptop after 45 days?")

    assert result["answer"].startswith("Opened electronics")
    payload = captured["payload"]
    assert payload["name"] == "answer-question"
    assert payload["status"] == "OK"
    assert [span["type"] for span in payload["spans"]] == ["RETRIEVER", "TOOL", "LLM"]
    assert payload["spans"][2]["provider"] == "openai"
    assert payload["spans"][2]["model_name"] == "gpt-test"
    assert payload["total_input_tokens"] == 12
    assert payload["total_output_tokens"] == 9


def test_openai_integration_records_llm_span(monkeypatch):
    captured = {}

    def fake_submit(_self, trace):
        captured["payload"] = trace.to_payload()

    monkeypatch.setattr(AgentGuard, "_submit_trace", fake_submit)

    class FakeCompletions:
        def create(self, **_kwargs):
            return SimpleNamespace(
                id="chatcmpl-test",
                model="gpt-test",
                usage=SimpleNamespace(prompt_tokens=11, completion_tokens=7),
                model_dump=lambda: {
                    "id": "chatcmpl-test",
                    "object": "chat.completion",
                    "model": "gpt-test",
                },
            )

    fake_openai = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    agentguard = AgentGuard(
        base_url="http://agentguard.test",
        project="support-agent",
        version="v1",
    )
    client = instrument_openai(fake_openai, agentguard=agentguard)

    with agentguard.trace("support-request"):
        response = client.chat.completions.create(
            model="gpt-test",
            messages=[{"role": "user", "content": "hello"}],
        )

    assert response.id == "chatcmpl-test"
    span = captured["payload"]["spans"][0]
    assert span["name"] == "openai.chat.completions.create"
    assert span["type"] == "LLM"
    assert span["provider"] == "openai-compatible"
    assert span["model_name"] == "gpt-test"
    assert span["input_tokens"] == 11
    assert span["output_tokens"] == 7


def test_async_trace_run_waits_for_completion(monkeypatch):
    captured = {}

    def fake_submit(_self, trace):
        captured["payload"] = trace.to_payload()

    monkeypatch.setattr(AgentGuard, "_submit_trace", fake_submit)
    client = AgentGuard(base_url="http://agentguard.test", project="async-app", version="v1")

    @client.trace_run("async-answer", input_arg="question")
    async def answer(*, question: str):
        await asyncio.sleep(0)
        return {"answer": question.upper()}

    result = asyncio.run(answer(question="hello"))
    assert result == {"answer": "HELLO"}
    assert captured["payload"]["output"] == result
    assert captured["payload"]["status"] == "OK"


def test_async_openai_integration_records_completed_response(monkeypatch):
    captured = {}

    def fake_submit(_self, trace):
        captured["payload"] = trace.to_payload()

    monkeypatch.setattr(AgentGuard, "_submit_trace", fake_submit)

    class FakeAsyncCompletions:
        async def create(self, **_kwargs):
            await asyncio.sleep(0)
            return SimpleNamespace(
                id="chatcmpl-async",
                model="gpt-async",
                usage=SimpleNamespace(prompt_tokens=5, completion_tokens=3),
                model_dump=lambda: {
                    "id": "chatcmpl-async",
                    "object": "chat.completion",
                    "model": "gpt-async",
                },
            )

    agentguard = AgentGuard(
        base_url="http://agentguard.test",
        project="async-app",
        version="v1",
    )
    wrapped = instrument_openai(
        SimpleNamespace(chat=SimpleNamespace(completions=FakeAsyncCompletions())),
        agentguard=agentguard,
    )

    async def run():
        with agentguard.trace("async-support"):
            return await wrapped.chat.completions.create(
                model="gpt-async",
                messages=[{"role": "user", "content": "hello"}],
            )

    response = asyncio.run(run())
    assert response.id == "chatcmpl-async"
    span = captured["payload"]["spans"][0]
    assert span["status"] == "OK"
    assert span["input_tokens"] == 5
    assert span["output_tokens"] == 3
