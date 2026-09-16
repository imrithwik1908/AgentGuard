from datetime import UTC, datetime, timedelta

import pytest

from agentguard_api.core.config import Settings
from agentguard_api.core.time import duration_ms
from agentguard_api.models.enums import RunStatus, SpanType
from agentguard_api.schemas.trace import SpanIngest, TraceIngest
from agentguard_api.services.errors import ValidationError
from agentguard_api.services.trace_ingestion import _validate_span_graph


def _now():
    return datetime(2026, 9, 12, 12, 0, tzinfo=UTC)


def _trace(spans):
    return TraceIngest(
        project_slug="research-agent",
        version="v1",
        name="answer-question",
        status=RunStatus.OK,
        started_at=_now(),
        ended_at=_now() + timedelta(seconds=1),
        spans=spans,
    )


def _span(external_span_id="root", parent_external_span_id=None, span_type=SpanType.LLM):
    return SpanIngest(
        external_span_id=external_span_id,
        parent_external_span_id=parent_external_span_id,
        type=span_type,
        name=external_span_id or "anonymous",
        status=RunStatus.OK,
        started_at=_now(),
        ended_at=_now() + timedelta(milliseconds=10),
    )


def test_duration_is_calculated_from_canonical_timestamps():
    assert duration_ms(_now(), _now() + timedelta(milliseconds=42)) == 42


def test_invalid_parent_is_rejected():
    payload = _trace([_span("child", "missing-parent")])

    with pytest.raises(ValidationError):
        _validate_span_graph(payload, max_spans=10)


def test_duplicate_external_span_id_is_rejected():
    payload = _trace([_span("same"), _span("same")])

    with pytest.raises(ValidationError):
        _validate_span_graph(payload, max_spans=10)


def test_span_limit_is_enforced():
    payload = _trace([_span("one"), _span("two")])

    with pytest.raises(ValidationError):
        _validate_span_graph(payload, max_spans=1)


def test_zero_root_spans_are_valid():
    payload = _trace([])

    _validate_span_graph(payload, max_spans=10)


def test_settings_expose_payload_safety_limits():
    settings = Settings(max_trace_spans=5, max_ingestion_bytes=20_000)

    assert settings.max_trace_spans == 5
    assert settings.max_ingestion_bytes == 20_000

