from __future__ import annotations

import inspect
from typing import Any

from agentguard.client import AgentGuard


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump()
        except TypeError:
            return value.model_dump(exclude_none=True)
    if hasattr(value, "dict"):
        return value.dict()
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    return {}


def _usage(response: Any) -> tuple[int | None, int | None]:
    usage = getattr(response, "usage", None)
    usage_dict = _as_dict(usage)
    input_tokens = usage_dict.get("prompt_tokens") or usage_dict.get("input_tokens")
    output_tokens = usage_dict.get("completion_tokens") or usage_dict.get("output_tokens")
    return input_tokens, output_tokens


def _response_metadata(response: Any) -> dict[str, Any]:
    data = _as_dict(response)
    return {
        key: data[key]
        for key in ("id", "object", "created", "model", "system_fingerprint")
        if key in data
    }


class _ChatCompletionsProxy:
    def __init__(self, wrapped: Any, agentguard: AgentGuard) -> None:
        self._wrapped = wrapped
        self._agentguard = agentguard

    def create(self, *args: Any, **kwargs: Any) -> Any:
        if inspect.iscoroutinefunction(self._wrapped.create):
            return self._record_async(args, kwargs)
        with self._span(kwargs) as span:
            response = self._wrapped.create(*args, **kwargs)
            input_tokens, output_tokens = _usage(response)
            span.set_attributes(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                response_metadata=_response_metadata(response),
            )
            span.set_output(_response_metadata(response))
            return response

    def _span(self, kwargs: dict[str, Any]):
        model = kwargs.get("model")
        request_metadata = {
            "model": model,
            "stream": kwargs.get("stream", False),
            "temperature": kwargs.get("temperature"),
            "tools_configured": bool(kwargs.get("tools")),
        }
        return self._agentguard.llm_call(
            "openai.chat.completions.create",
            provider="openai-compatible",
            model=str(model) if model is not None else None,
            input={
                "messages": kwargs.get("messages"),
                "response_format": kwargs.get("response_format"),
            },
            metadata=request_metadata,
        )

    async def _record_async(self, args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
        with self._span(kwargs) as span:
            response = await self._wrapped.create(*args, **kwargs)
            input_tokens, output_tokens = _usage(response)
            span.set_attributes(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                response_metadata=_response_metadata(response),
            )
            span.set_output(_response_metadata(response))
            return response

    def __getattr__(self, name: str) -> Any:
        return getattr(self._wrapped, name)


class _ChatProxy:
    def __init__(self, wrapped: Any, agentguard: AgentGuard) -> None:
        self._wrapped = wrapped
        self.completions = _ChatCompletionsProxy(wrapped.completions, agentguard)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._wrapped, name)


class OpenAIInstrumentedClient:
    def __init__(self, wrapped: Any, agentguard: AgentGuard) -> None:
        self._wrapped = wrapped
        self.chat = _ChatProxy(wrapped.chat, agentguard)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._wrapped, name)


def instrument_openai(client: Any, *, agentguard: AgentGuard) -> OpenAIInstrumentedClient:
    return OpenAIInstrumentedClient(client, agentguard)
