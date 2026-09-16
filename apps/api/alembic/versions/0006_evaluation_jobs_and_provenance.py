"""Add evaluator provenance and evaluation job queue tables.

Revision ID: 0006_eval_jobs
Revises: 0005_auth_sessions
Create Date: 2026-09-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_eval_jobs"
down_revision: str | None = "0005_auth_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


evaluation_method = postgresql.ENUM(
    "DETERMINISTIC_BEHAVIORAL",
    "DETERMINISTIC_OPERATIONAL",
    "RETRIEVAL",
    "LLM_JUDGE",
    "INSTRUMENTATION_ONLY",
    name="evaluation_method",
    create_type=False,
)
evaluation_job_status = postgresql.ENUM(
    "QUEUED",
    "RUNNING",
    "COMPLETED",
    "PARTIAL",
    "FAILED",
    name="evaluation_job_status",
    create_type=False,
)
evaluation_job_case_status = postgresql.ENUM(
    "QUEUED",
    "RUNNING",
    "COMPLETED",
    "FAILED",
    name="evaluation_job_case_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    evaluation_method.create(bind, checkfirst=True)
    evaluation_job_status.create(bind, checkfirst=True)
    evaluation_job_case_status.create(bind, checkfirst=True)

    op.add_column(
        "evaluation_results",
        sa.Column("evaluator_version", sa.String(length=80), nullable=False, server_default="1.0.0"),
    )
    op.add_column(
        "evaluation_results",
        sa.Column(
            "method",
            evaluation_method,
            nullable=False,
            server_default="DETERMINISTIC_BEHAVIORAL",
        ),
    )
    op.add_column(
        "evaluation_results",
        sa.Column(
            "rubric",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column("evaluation_results", sa.Column("judge_model", sa.String(length=200), nullable=True))

    op.create_table(
        "evaluation_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("request_id", sa.String(length=120), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evaluator_name", sa.String(length=160), nullable=False),
        sa.Column("status", evaluation_job_status, nullable=False),
        sa.Column("total_cases", sa.Integer(), nullable=False),
        sa.Column("completed_cases", sa.Integer(), nullable=False),
        sa.Column("failed_cases", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("error", postgresql.JSONB(none_as_null=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["application_version_id"],
            ["application_versions.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "dataset_id",
            "application_version_id",
            "evaluator_name",
            "request_id",
            name="uq_evaluation_jobs_request",
        ),
    )
    op.create_index("ix_evaluation_jobs_project_id", "evaluation_jobs", ["project_id"])
    op.create_index("ix_evaluation_jobs_dataset_id", "evaluation_jobs", ["dataset_id"])
    op.create_index(
        "ix_evaluation_jobs_application_version_id",
        "evaluation_jobs",
        ["application_version_id"],
    )
    op.create_index("ix_evaluation_jobs_status", "evaluation_jobs", ["status"])
    op.create_index("ix_evaluation_jobs_created_at", "evaluation_jobs", ["created_at"])

    op.create_table(
        "evaluation_job_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dataset_case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("evaluation_result_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", evaluation_job_case_status, nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error", postgresql.JSONB(none_as_null=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["evaluation_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["dataset_case_id"], ["dataset_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["trace_id"], ["traces.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["evaluation_result_id"],
            ["evaluation_results.id"],
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("job_id", "dataset_case_id", name="uq_evaluation_job_cases_case"),
    )
    op.create_index("ix_evaluation_job_cases_job_id", "evaluation_job_cases", ["job_id"])
    op.create_index(
        "ix_evaluation_job_cases_dataset_case_id",
        "evaluation_job_cases",
        ["dataset_case_id"],
    )
    op.create_index("ix_evaluation_job_cases_status", "evaluation_job_cases", ["status"])


def downgrade() -> None:
    op.drop_index("ix_evaluation_job_cases_status", table_name="evaluation_job_cases")
    op.drop_index("ix_evaluation_job_cases_dataset_case_id", table_name="evaluation_job_cases")
    op.drop_index("ix_evaluation_job_cases_job_id", table_name="evaluation_job_cases")
    op.drop_table("evaluation_job_cases")

    op.drop_index("ix_evaluation_jobs_created_at", table_name="evaluation_jobs")
    op.drop_index("ix_evaluation_jobs_status", table_name="evaluation_jobs")
    op.drop_index("ix_evaluation_jobs_application_version_id", table_name="evaluation_jobs")
    op.drop_index("ix_evaluation_jobs_dataset_id", table_name="evaluation_jobs")
    op.drop_index("ix_evaluation_jobs_project_id", table_name="evaluation_jobs")
    op.drop_table("evaluation_jobs")

    op.drop_column("evaluation_results", "judge_model")
    op.drop_column("evaluation_results", "rubric")
    op.drop_column("evaluation_results", "method")
    op.drop_column("evaluation_results", "evaluator_version")

    bind = op.get_bind()
    evaluation_job_case_status.drop(bind, checkfirst=True)
    evaluation_job_status.drop(bind, checkfirst=True)
    evaluation_method.drop(bind, checkfirst=True)
