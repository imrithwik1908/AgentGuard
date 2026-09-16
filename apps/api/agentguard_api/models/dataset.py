import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agentguard_api.core.time import utc_now
from agentguard_api.db.base import Base


class Dataset(Base):
    __tablename__ = "datasets"
    __table_args__ = (
        UniqueConstraint("project_id", "slug", name="uq_datasets_project_slug"),
        Index("ix_datasets_project_id", "project_id"),
        Index("ix_datasets_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    project = relationship("Project")
    cases = relationship("DatasetCase", back_populates="dataset", cascade="all, delete-orphan")


class DatasetCase(Base):
    __tablename__ = "dataset_cases"
    __table_args__ = (
        UniqueConstraint("dataset_id", "name", name="uq_dataset_cases_dataset_name"),
        Index("ix_dataset_cases_dataset_id", "dataset_id"),
        Index("ix_dataset_cases_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    input: Mapped[Any] = mapped_column(JSONB, nullable=False)
    expected_output: Mapped[Any | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    expected_substring: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    dataset = relationship("Dataset", back_populates="cases")
    evaluations = relationship("EvaluationResult", back_populates="dataset_case")
