import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agentguard_api.core.time import utc_now
from agentguard_api.db.base import Base
from agentguard_api.models.enums import RunStatus, SpanType


class Span(Base):
    __tablename__ = "spans"
    __table_args__ = (
        Index(
            "uq_spans_trace_external_span_id",
            "trace_id",
            "external_span_id",
            unique=True,
            postgresql_where="external_span_id IS NOT NULL",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("traces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_span_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spans.id", ondelete="CASCADE"), nullable=True, index=True
    )
    external_span_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    type: Mapped[SpanType] = mapped_column(Enum(SpanType, name="span_type"), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus, name="span_status"), nullable=False)
    input: Mapped[Any | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    output: Mapped[Any | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    provider: Mapped[str | None] = mapped_column(String(120), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    trace = relationship("Trace", back_populates="spans")
    parent = relationship("Span", remote_side=[id])
