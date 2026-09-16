from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from agentguard_api.models.enums import RunStatus, SpanType

JsonValue = Any


class ApiError(BaseModel):
    type: str
    message: str
    code: str | None = None
    metadata: dict[str, JsonValue] | None = None


class CapturedError(BaseModel):
    type: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1)
    stacktrace: str | None = None
    code: str | None = Field(default=None, max_length=120)
    metadata: dict[str, JsonValue] | None = None


class SpanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    trace_id: UUID
    parent_span_id: UUID | None
    external_span_id: str | None
    type: SpanType
    name: str
    status: RunStatus
    input: JsonValue | None
    output: JsonValue | None
    metadata: dict[str, JsonValue] = Field(validation_alias="meta", serialization_alias="metadata")
    attributes: dict[str, JsonValue]
    provider: str | None
    model_name: str | None
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost: Decimal | None
    started_at: datetime
    ended_at: datetime
    duration_ms: int
    error: dict[str, JsonValue] | None
    created_at: datetime


class TraceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    application_version_id: UUID
    external_trace_id: str | None
    name: str
    status: RunStatus
    input: JsonValue | None
    output: JsonValue | None
    metadata: dict[str, JsonValue] = Field(validation_alias="meta", serialization_alias="metadata")
    started_at: datetime
    ended_at: datetime
    duration_ms: int
    total_input_tokens: int | None
    total_output_tokens: int | None
    estimated_cost: Decimal | None
    error: dict[str, JsonValue] | None
    created_at: datetime
    spans: list[SpanRead] = []
