import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agentguard_api.core.time import utc_now
from agentguard_api.db.base import Base
from agentguard_api.models.enums import RunStatus


class Trace(Base):
    __tablename__ = "traces"
    __table_args__ = (
        Index(
            "uq_traces_project_external_trace_id",
            "project_id",
            "external_trace_id",
            unique=True,
            postgresql_where="external_trace_id IS NOT NULL",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    application_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("application_versions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    external_trace_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus, name="trace_status"), nullable=False)
    input: Mapped[Any | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    output: Mapped[Any | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    total_input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    project = relationship("Project", back_populates="traces")
    application_version = relationship("ApplicationVersion", back_populates="traces")
    spans = relationship("Span", back_populates="trace", cascade="all, delete-orphan")
    evaluations = relationship(
        "EvaluationResult",
        back_populates="trace",
        cascade="all, delete-orphan",
    )
