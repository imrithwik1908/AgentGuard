# AgentGuard Python SDK

AgentGuard is an AI application regression-testing and reliability platform.

The Python SDK connects your AI/LLM/RAG/agent application to AgentGuard so the web app can evaluate versions, identify regressions, investigate failures, and support release decisions.

## Install

```bash
python -m pip install agentguard-reliability
```

Import:

```python
from agentguard import AgentGuard
```

## Quickstart

```python
from agentguard import AgentGuard

client = AgentGuard(
    base_url="https://your-agentguard-api.example.com",
    project="support-agent",
    version="candidate-v2",
)

with client.trace("answer-question", input={"question": question}) as trace:
    with trace.span("retrieve", type="RETRIEVER", input={"question": question}) as span:
        docs = retrieve(question)
        span.set_output({"documents": docs})

    with trace.span("generate", type="LLM", input={"question": question, "documents": docs}) as span:
        answer = generate(question, docs)
        span.set_attributes(provider="openai", model_name="gpt-4o-mini")
        span.set_output({"answer": answer})

    trace.set_output({"answer": answer})
```

## What Gets Recorded

- Project and version.
- One run per traced application execution.
- Nested steps such as retrieval, model calls, tool calls, and custom logic.
- Inputs and outputs.
- Runtime status.
- Errors and stack traces.
- Provider/model metadata.
- Token and cost metadata when supplied.

## How This Supports Regression Testing

1. Register a baseline version and a candidate version in AgentGuard.
2. Run the same behavioral test cases against both versions.
3. AgentGuard pairs each case across versions.
4. AgentGuard classifies each case as regressed, improved, unchanged, or not comparable.
5. Use the web app to investigate failed runs and decide whether to ship.

## Concepts

- Project: one AI application.
- Version: one behavior snapshot of that application.
- Run: one complete execution of the AI application.
- Step: one recorded operation inside a run, such as retrieval, a model call, or a tool call.
- Regression: a case that worked better in the baseline than in the candidate.
- Evaluator: a check that measures whether a run behaved as expected.

## Failure Behavior

By default, SDK submission failures do not crash your application. AgentGuard logs a structured warning and drops failed telemetry.

Use `raise_on_failure=True` only when you want instrumentation failures to raise exceptions during development or CI.

```python
client = AgentGuard(
    base_url="https://your-agentguard-api.example.com",
    project="support-agent",
    version="candidate-v2",
    raise_on_failure=True,
)
```

## Development

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
ruff check agentguard tests
```

## Documentation

Full repository docs include:

- getting started guide;
- core concepts;
- SDK reference;
- web app guide;
- evaluation semantics;
- real LLM demo guide;
- PyPI publishing guide.
