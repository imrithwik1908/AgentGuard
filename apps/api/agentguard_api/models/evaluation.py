import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agentguard_api.core.time import utc_now
from agentguard_api.db.base import Base
from agentguard_api.models.enums import (
    EvaluationJobCaseStatus,
    EvaluationJobStatus,
    EvaluationMethod,
    EvaluationStatus,
)


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"
    __table_args__ = (
        UniqueConstraint(
            "trace_id",
            "evaluator_name",
            name="uq_evaluation_results_trace_evaluator",
        ),
        Index("ix_evaluation_results_project_id", "project_id"),
        Index("ix_evaluation_results_application_version_id", "application_version_id"),
        Index("ix_evaluation_results_trace_id", "trace_id"),
        Index("ix_evaluation_results_dataset_id", "dataset_id"),
        Index("ix_evaluation_results_dataset_case_id", "dataset_case_id"),
        Index("ix_evaluation_results_status", "status"),
        Index("ix_evaluation_results_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    dataset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="SET NULL"),
        nullable=True,
    )
    dataset_case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dataset_cases.id", ondelete="SET NULL"),
        nullable=True,
    )
    application_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("application_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    trace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("traces.id", ondelete="CASCADE"),
        nullable=False,
    )
    evaluator_name: Mapped[str] = mapped_column(String(160), nullable=False)
    evaluator_version: Mapped[str] = mapped_column(String(80), nullable=False, default="1.0.0")
    method: Mapped[EvaluationMethod] = mapped_column(
        Enum(EvaluationMethod, name="evaluation_method"),
        nullable=False,
        default=EvaluationMethod.DETERMINISTIC_BEHAVIORAL,
    )
    rubric: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    judge_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    score: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    threshold: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    status: Mapped[EvaluationStatus] = mapped_column(
        Enum(EvaluationStatus, name="evaluation_status"),
        nullable=False,
    )
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    label: Mapped[str | None] = mapped_column(String(160), nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    project = relationship("Project")
    application_version = relationship("ApplicationVersion")
    trace = relationship("Trace", back_populates="evaluations")
    dataset_case = relationship("DatasetCase", back_populates="evaluations")


class EvaluationJob(Base):
    __tablename__ = "evaluation_jobs"
    __table_args__ = (
        UniqueConstraint(
            "dataset_id",
            "application_version_id",
            "evaluator_name",
            "request_id",
            name="uq_evaluation_jobs_request",
        ),
        Index("ix_evaluation_jobs_project_id", "project_id"),
        Index("ix_evaluation_jobs_dataset_id", "dataset_id"),
        Index("ix_evaluation_jobs_application_version_id", "application_version_id"),
        Index("ix_evaluation_jobs_status", "status"),
        Index("ix_evaluation_jobs_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id: Mapped[str] = mapped_column(String(120), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
    )
    application_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("application_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    evaluator_name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[EvaluationJobStatus] = mapped_column(
        Enum(EvaluationJobStatus, name="evaluation_job_status"),
        nullable=False,
        default=EvaluationJobStatus.QUEUED,
    )
    total_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    cases = relationship(
        "EvaluationJobCase",
        back_populates="job",
        cascade="all, delete-orphan",
    )


class EvaluationJobCase(Base):
    __tablename__ = "evaluation_job_cases"
    __table_args__ = (
        UniqueConstraint("job_id", "dataset_case_id", name="uq_evaluation_job_cases_case"),
        Index("ix_evaluation_job_cases_job_id", "job_id"),
        Index("ix_evaluation_job_cases_dataset_case_id", "dataset_case_id"),
        Index("ix_evaluation_job_cases_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluation_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    dataset_case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dataset_cases.id", ondelete="CASCADE"),
        nullable=False,
    )
    trace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("traces.id", ondelete="SET NULL"),
        nullable=True,
    )
    evaluation_result_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluation_results.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[EvaluationJobCaseStatus] = mapped_column(
        Enum(EvaluationJobCaseStatus, name="evaluation_job_case_status"),
        nullable=False,
        default=EvaluationJobCaseStatus.QUEUED,
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    job = relationship("EvaluationJob", back_populates="cases")
    dataset_case = relationship("DatasetCase")
