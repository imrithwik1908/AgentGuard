from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator

from agentguard_api.models.enums import RunStatus, SpanType
from agentguard_api.schemas.common import CapturedError, TraceRead


class SpanIngest(BaseModel):
    external_span_id: str | None = Field(default=None, max_length=200)
    parent_external_span_id: str | None = Field(default=None, max_length=200)
    type: SpanType
    name: str = Field(min_length=1, max_length=300)
    status: RunStatus = RunStatus.UNSET
    input: Any | None = None
    output: Any | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    attributes: dict[str, Any] = Field(default_factory=dict)
    provider: str | None = Field(default=None, max_length=120)
    model_name: str | None = Field(default=None, max_length=200)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    estimated_cost: Decimal | None = Field(default=None, ge=0)
    started_at: datetime
    ended_at: datetime
    error: CapturedError | None = None

    @field_validator("started_at", "ended_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return value


class TraceIngest(BaseModel):
    project_slug: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=120)
    external_trace_id: str | None = Field(default=None, max_length=200)
    name: str = Field(min_length=1, max_length=300)
    status: RunStatus = RunStatus.UNSET
    input: Any | None = None
    output: Any | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime
    ended_at: datetime
    total_input_tokens: int | None = Field(default=None, ge=0)
    total_output_tokens: int | None = Field(default=None, ge=0)
    estimated_cost: Decimal | None = Field(default=None, ge=0)
    error: CapturedError | None = None
    spans: list[SpanIngest] = Field(default_factory=list)

    @field_validator("started_at", "ended_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return value


class TraceList(BaseModel):
    items: list[TraceRead]
    limit: int
    offset: int
    total: int

