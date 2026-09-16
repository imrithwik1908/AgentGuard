# Python SDK

The AgentGuard SDK connects an AI application to the AgentGuard backend.

It records:

- project and version;
- run input and output;
- internal steps;
- parent-child step nesting;
- timestamps and duration;
- status;
- errors and stack traces;
- provider/model metadata;
- token and cost metadata when supplied.

## Installation

Install from the public GitHub repository:

```bash
python -m pip install "agentguard-reliability @ git+https://github.com/imrithwik1908/AgentGuard.git#subdirectory=packages/python-sdk"
```

For local repository development:

```bash
python -m pip install -e "/path/to/AgentGuard/packages/python-sdk"
```

Import:

```python
from agentguard import AgentGuard
```

## Client

```python
client = AgentGuard(
    base_url="http://127.0.0.1:8000",
    project="support-agent",
    version="candidate-v2",
    api_key=None,
    raise_on_failure=False,
)
```

Parameters:

- `base_url`: AgentGuard API URL.
- `project`: project slug.
- `version`: application version string.
- `api_key`: optional API key when backend auth is enabled.
- `raise_on_failure`: whether SDK submission failures should raise.
- `timeout_seconds`: HTTP timeout for telemetry submission.

Default behavior is fail-open: if AgentGuard is unreachable, the SDK logs a structured warning and does not crash the user's AI application.

## API Reference

### `AgentGuard`

```python
AgentGuard(
    *,
    base_url: str,
    project: str,
    version: str,
    api_key: str | None = None,
    raise_on_failure: bool = False,
    timeout_seconds: float = 5.0,
)
```

Creates an SDK client for one project/version pair.

Use one client per application version. If your process serves multiple versions at once, create a client for each version.

### `AgentGuard.trace`

```python
client.trace(
    name: str,
    *,
    input: Any | None = None,
    metadata: dict[str, Any] | None = None,
    external_trace_id: str | None = None,
)
```

Returns a context manager for one complete run.

Use `external_trace_id` when you already have a request id, job id, or idempotency key. It helps connect AgentGuard telemetry to your own logs.

### `TraceContext.span`

```python
trace.span(
    name: str,
    *,
    type: str,
    input: Any | None = None,
    metadata: dict[str, Any] | None = None,
    attributes: dict[str, Any] | None = None,
)
```

Returns a context manager for one internal step.

Common step types:

| Type | Use for |
| --- | --- |
| `LLM` | model generation or chat completion |
| `RETRIEVER` | vector search, keyword search, hybrid retrieval |
| `TOOL` | external tool or function call |
| `EMBEDDING` | embedding model call |
| `RERANKER` | reranking retrieved documents |
| `CHAIN` | composed application logic |
| `AGENT` | agent loop or top-level agent step |
| `CUSTOM` | app-specific operation |

### `TraceContext.set_output`

```python
trace.set_output({"answer": answer})
```

Stores the final run output.

### `TraceContext.set_status`

```python
trace.set_status("OK")
trace.set_status("ERROR")
```

Normally the SDK sets this automatically. Use manual status only when your app handles an error internally but still wants to mark the run.

### `TraceContext.set_error`

```python
trace.set_error(
    type="ValidationError",
    message="model returned invalid JSON",
    code="invalid_json",
    metadata={"schema": "ticket_response"},
)
```

Use when an error is handled rather than raised.

### `SpanContext.set_output`

```python
span.set_output({"documents": docs})
```

Stores output for one step.

### `SpanContext.set_attributes`

```python
span.set_attributes(
    provider="openai",
    model_name="gpt-4o-mini",
    input_tokens=120,
    output_tokens=45,
    estimated_cost=Decimal("0.0002"),
    top_k=5,
)
```

Stores provider/model/token/cost metadata plus custom attributes.

### `SpanContext.set_error`

```python
span.set_error(
    type="ToolError",
    message="CRM lookup failed",
    code="crm_timeout",
    metadata={"tool": "crm_lookup"},
)
```

Use when a step-level error is handled inside your app.

## Trace Context

Use a trace for one full AI application execution:

```python
with client.trace("answer-question", input={"question": question}) as trace:
    ...
    trace.set_output({"answer": answer})
```

Trace fields:

- `name`: human-readable run name.
- `input`: run input.
- `output`: run output.
- `metadata`: custom metadata.
- `external_trace_id`: optional idempotency-friendly external identifier.

Recommended trace names:

- `answer-question`
- `run-agent`
- `summarize-document`
- `classify-ticket`
- `retrieve-and-answer`

Prefer stable, human-readable names over UUIDs.

## Step Context

Use a step for important internal operations:

```python
with trace.span("retrieve", type="RETRIEVER", input={"question": question}) as span:
    docs = retrieve(question)
    span.set_output({"documents": docs})
```

Supported step types:

- `AGENT`
- `LLM`
- `RETRIEVER`
- `TOOL`
- `CHAIN`
- `EMBEDDING`
- `RERANKER`
- `CUSTOM`

The SDK method is currently named `span` because the backend stores span-like records. The UI calls them steps.

Recommended step names:

- `retrieve policy context`
- `generate answer`
- `call search tool`
- `parse structured output`
- `rerank documents`

## Model Metadata

```python
span.set_attributes(
    provider="openai",
    model_name="gpt-4o-mini",
    input_tokens=120,
    output_tokens=45,
    estimated_cost=Decimal("0.0002"),
)
```

Cost uses decimal data, not binary floating point.

## Error Capture

If an exception happens inside a trace or step, the SDK captures:

- error type;
- message;
- stacktrace;
- optional code;
- optional metadata.

The original exception is re-raised so the application keeps normal Python behavior.

```python
with client.trace("answer-question") as trace:
    with trace.span("generate", type="LLM"):
        raise RuntimeError("model call failed")
```

The trace and step are marked `ERROR`.

## Concurrency

The SDK uses `contextvars.ContextVar` to track the active trace and nested step stack.

This is safer than a process-global mutable `current_span` because concurrent or async executions should not overwrite each other's active context.

## Submission Failure

Default:

```python
AgentGuard(..., raise_on_failure=False)
```

If the AgentGuard backend is down, your AI app keeps running and telemetry is discarded for Phase 1.

Strict mode:

```python
AgentGuard(..., raise_on_failure=True)
```

Use this in local development or CI when instrumentation failure should fail loudly.

## Complete RAG Example

```python
from decimal import Decimal

from agentguard import AgentGuard


guard = AgentGuard(
    base_url="http://127.0.0.1:8000",
    project="support-agent",
    version="candidate-v2",
)


def answer_question(question: str) -> str:
    with guard.trace("answer-question", input={"question": question}) as trace:
        with trace.span("retrieve policy context", type="RETRIEVER", input={"question": question}) as span:
            docs = retrieve_documents(question)
            span.set_output({"documents": docs})
            span.set_attributes(top_k=len(docs), retriever="hybrid-search")

        with trace.span("generate answer", type="LLM", input={"question": question, "documents": docs}) as span:
            answer = call_model(question, docs)
            span.set_output({"answer": answer})
            span.set_attributes(
                provider="openai",
                model_name="gpt-4o-mini",
                input_tokens=142,
                output_tokens=58,
                estimated_cost=Decimal("0.0003"),
            )

        trace.set_output({"answer": answer})
        return answer
```

## Best Practices

- Instrument the user-visible unit of work as one trace.
- Record important internal operations as steps.
- Prefer human-readable names.
- Store enough input/output to investigate failures.
- Avoid logging secrets or sensitive user data unless redaction is configured.
- Use stable project slugs and version names.
- Keep `raise_on_failure=False` in production unless you intentionally want telemetry failures to break the app.
