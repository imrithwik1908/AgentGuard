from __future__ import annotations

import contextvars
import functools
import inspect
import json
import logging
import ssl
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from urllib import error, request

import certifi

logger = logging.getLogger("agentguard")
_HTTPS_CONTEXT = ssl.create_default_context(cafile=certifi.where())

_current_trace: contextvars.ContextVar[TraceContext | None] = contextvars.ContextVar(
    "agentguard_current_trace", default=None
)
_span_stack: contextvars.ContextVar[tuple[SpanContext, ...]] = contextvars.ContextVar(
    "agentguard_span_stack", default=()
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _duration_ms(started_at: datetime, ended_at: datetime) -> int:
    return int((ended_at - started_at).total_seconds() * 1000)


def _capture_error(exc_type: type[BaseException], exc: BaseException, tb) -> dict[str, Any]:
    return {
        "type": exc_type.__name__,
        "message": str(exc),
        "stacktrace": "".join(traceback.format_exception(exc_type, exc, tb)),
        "code": None,
        "metadata": None,
    }


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


@dataclass
class SpanRecord:
    external_span_id: str
    parent_external_span_id: str | None
    type: str
    name: str
    status: str
    input: Any | None
    output: Any | None
    metadata: dict[str, Any]
    attributes: dict[str, Any]
    provider: str | None
    model_name: str | None
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost: Decimal | None
    started_at: datetime
    ended_at: datetime
    error: dict[str, Any] | None

    def to_payload(self) -> dict[str, Any]:
        return {
            "external_span_id": self.external_span_id,
            "parent_external_span_id": self.parent_external_span_id,
            "type": self.type,
            "name": self.name,
            "status": self.status,
            "input": self.input,
            "output": self.output,
            "metadata": self.metadata,
            "attributes": self.attributes,
            "provider": self.provider,
            "model_name": self.model_name,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "estimated_cost": self.estimated_cost,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "error": self.error,
        }


@dataclass
class TraceContext:
    client: AgentGuard
    name: str
    input: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    external_trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: datetime = field(default_factory=_utc_now)
    ended_at: datetime | None = None
    output: Any | None = None
    status: str = "UNSET"
    error: dict[str, Any] | None = None
    spans: list[SpanRecord] = field(default_factory=list)
    _trace_token: contextvars.Token | None = None
    _stack_token: contextvars.Token | None = None

    def __enter__(self) -> TraceContext:
        self._trace_token = _current_trace.set(self)
        self._stack_token = _span_stack.set(())
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.ended_at = _utc_now()
        if exc_type is not None:
            self.status = "ERROR"
            self.error = _capture_error(exc_type, exc, tb)
        elif self.status == "UNSET":
            self.status = "OK"

        try:
            self.client._submit_trace(self)
        finally:
            if self._stack_token is not None:
                _span_stack.reset(self._stack_token)
            if self._trace_token is not None:
                _current_trace.reset(self._trace_token)
        return False

    def span(
        self,
        name: str,
        *,
        type: str,
        input: Any | None = None,
        metadata: dict[str, Any] | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> SpanContext:
        return SpanContext(
            trace=self,
            name=name,
            type=type,
            input=input,
            metadata=metadata or {},
            attributes=attributes or {},
        )

    def llm_call(
        self,
        name: str = "llm.call",
        *,
        provider: str | None = None,
        model: str | None = None,
        input: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SpanContext:
        span = self.span(name, type="LLM", input=input, metadata=metadata)
        span.provider = provider
        span.model_name = model
        return span

    def retrieval(
        self,
        name: str = "retrieval",
        *,
        query: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SpanContext:
        return self.span(name, type="RETRIEVER", input=query, metadata=metadata)

    def tool(
        self,
        name: str,
        *,
        arguments: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SpanContext:
        return self.span(name, type="TOOL", input=arguments, metadata=metadata)

    def set_output(self, output: Any) -> None:
        self.output = output

    def set_status(self, status: str) -> None:
        self.status = status

    def set_error(
        self,
        *,
        type: str,
        message: str,
        code: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        self.status = "ERROR"
        self.error = {
            "type": type,
            "message": message,
            "stacktrace": None,
            "code": code,
            "metadata": metadata,
        }

    def to_payload(self) -> dict[str, Any]:
        ended_at = self.ended_at or _utc_now()
        total_input_tokens = sum(
            span.input_tokens or 0 for span in self.spans if span.input_tokens is not None
        )
        total_output_tokens = sum(
            span.output_tokens or 0 for span in self.spans if span.output_tokens is not None
        )
        return {
            "project_slug": self.client.project,
            "version": self.client.version,
            "external_trace_id": self.external_trace_id,
            "name": self.name,
            "status": self.status,
            "input": self.input,
            "output": self.output,
            "metadata": self.metadata,
            "started_at": self.started_at,
            "ended_at": ended_at,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "estimated_cost": None,
            "error": self.error,
            "spans": [
                span.to_payload()
                for span in sorted(self.spans, key=lambda span: (span.started_at, span.ended_at))
            ],
        }


@dataclass
class SpanContext:
    trace: TraceContext
    name: str
    type: str
    input: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    attributes: dict[str, Any] = field(default_factory=dict)
    external_span_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: datetime | None = None
    output: Any | None = None
    status: str = "UNSET"
    error: dict[str, Any] | None = None
    provider: str | None = None
    model_name: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost: Decimal | None = None
    _stack_token: contextvars.Token | None = None

    def __enter__(self) -> SpanContext:
        if _current_trace.get() is not self.trace:
            raise RuntimeError("span must be entered inside its owning trace context")
        self.started_at = _utc_now()
        stack = _span_stack.get()
        self._stack_token = _span_stack.set((*stack, self))
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        ended_at = _utc_now()
        if exc_type is not None:
            self.status = "ERROR"
            self.error = _capture_error(exc_type, exc, tb)
        elif self.status == "UNSET":
            self.status = "OK"

        stack = _span_stack.get()
        parent = stack[-2] if len(stack) >= 2 else None
        if self.started_at is None:
            self.started_at = ended_at

        self.trace.spans.append(
            SpanRecord(
                external_span_id=self.external_span_id,
                parent_external_span_id=parent.external_span_id if parent else None,
                type=self.type,
                name=self.name,
                status=self.status,
                input=self.input,
                output=self.output,
                metadata=self.metadata,
                attributes=self.attributes,
                provider=self.provider,
                model_name=self.model_name,
                input_tokens=self.input_tokens,
                output_tokens=self.output_tokens,
                estimated_cost=self.estimated_cost,
                started_at=self.started_at,
                ended_at=ended_at,
                error=self.error,
            )
        )

        if self._stack_token is not None:
            _span_stack.reset(self._stack_token)
        return False

    def set_output(self, output: Any) -> None:
        self.output = output

    def set_attributes(
        self,
        *,
        provider: str | None = None,
        model_name: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        estimated_cost: Decimal | None = None,
        **attributes: Any,
    ) -> None:
        self.provider = provider if provider is not None else self.provider
        self.model_name = model_name if model_name is not None else self.model_name
        self.input_tokens = input_tokens if input_tokens is not None else self.input_tokens
        self.output_tokens = output_tokens if output_tokens is not None else self.output_tokens
        self.estimated_cost = estimated_cost if estimated_cost is not None else self.estimated_cost
        self.attributes.update(attributes)

    def set_error(
        self,
        *,
        type: str,
        message: str,
        code: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        self.status = "ERROR"
        self.error = {
            "type": type,
            "message": message,
            "stacktrace": None,
            "code": code,
            "metadata": metadata,
        }


class AgentGuard:
    def __init__(
        self,
        *,
        base_url: str,
        project: str,
        version: str,
        api_key: str | None = None,
        raise_on_failure: bool = False,
        timeout_seconds: float = 5.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.project = project
        self.version = version
        self.api_key = api_key
        self.raise_on_failure = raise_on_failure
        self.timeout_seconds = timeout_seconds

    def trace(
        self,
        name: str,
        *,
        input: Any | None = None,
        metadata: dict[str, Any] | None = None,
        external_trace_id: str | None = None,
    ) -> TraceContext:
        return TraceContext(
            client=self,
            name=name,
            input=input,
            metadata=metadata or {},
            external_trace_id=external_trace_id or str(uuid.uuid4()),
        )

    def current_trace(self) -> TraceContext | None:
        return _current_trace.get()

    def trace_run(
        self,
        name: str | None = None,
        *,
        input_arg: str | None = None,
        metadata: dict[str, Any] | None = None,
        external_trace_id_arg: str | None = None,
    ):
        def decorator(func):
            if inspect.iscoroutinefunction(func):

                @functools.wraps(func)
                async def async_wrapper(*args, **kwargs):
                    trace_input = (
                        kwargs.get(input_arg) if input_arg else (args[0] if args else None)
                    )
                    external_trace_id = (
                        str(kwargs.get(external_trace_id_arg))
                        if external_trace_id_arg and kwargs.get(external_trace_id_arg) is not None
                        else None
                    )
                    with self.trace(
                        name or func.__name__,
                        input=trace_input,
                        metadata=metadata,
                        external_trace_id=external_trace_id,
                    ) as trace:
                        output = await func(*args, **kwargs)
                        trace.set_output(output)
                        return output

                return async_wrapper

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                trace_input = None
                if input_arg:
                    trace_input = kwargs.get(input_arg)
                elif args:
                    trace_input = args[0]
                external_trace_id = (
                    str(kwargs.get(external_trace_id_arg))
                    if external_trace_id_arg and kwargs.get(external_trace_id_arg) is not None
                    else None
                )
                with self.trace(
                    name or func.__name__,
                    input=trace_input,
                    metadata=metadata,
                    external_trace_id=external_trace_id,
                ) as trace:
                    output = func(*args, **kwargs)
                    trace.set_output(output)
                    return output

            return wrapper

        return decorator

    def llm_call(
        self,
        name: str = "llm.call",
        *,
        provider: str | None = None,
        model: str | None = None,
        input: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SpanContext:
        trace = _current_trace.get()
        if trace is None:
            raise RuntimeError("llm_call must be used inside an AgentGuard trace")
        return trace.llm_call(name, provider=provider, model=model, input=input, metadata=metadata)

    def retrieval(
        self,
        name: str = "retrieval",
        *,
        query: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SpanContext:
        trace = _current_trace.get()
        if trace is None:
            raise RuntimeError("retrieval must be used inside an AgentGuard trace")
        return trace.retrieval(name, query=query, metadata=metadata)

    def tool(
        self,
        name: str,
        *,
        arguments: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SpanContext:
        trace = _current_trace.get()
        if trace is None:
            raise RuntimeError("tool must be used inside an AgentGuard trace")
        return trace.tool(name, arguments=arguments, metadata=metadata)

    def _submit_trace(self, trace: TraceContext) -> None:
        payload = json.dumps(trace.to_payload(), default=_json_default).encode("utf-8")
        headers = {"content-type": "application/json", "user-agent": "agentguard-python/0.1.0"}
        if self.api_key:
            headers["x-agentguard-api-key"] = self.api_key
        req = request.Request(
            f"{self.base_url}/api/v1/traces",
            data=payload,
            headers=headers,
            method="POST",
        )
        try:
            with request.urlopen(
                req,
                timeout=self.timeout_seconds,
                context=_HTTPS_CONTEXT,
            ) as response:
                if response.status >= 400:
                    raise RuntimeError(f"AgentGuard ingestion failed with HTTP {response.status}")
        except (error.URLError, TimeoutError, RuntimeError) as exc:
            logger.warning(
                "agentguard_trace_submission_failed",
                extra={
                    "agentguard": {
                        "project": self.project,
                        "version": self.version,
                        "trace_name": trace.name,
                        "external_trace_id": trace.external_trace_id,
                        "error": str(exc),
                    }
                },
            )
            if self.raise_on_failure:
                raise
