"""Add evaluation results.

Revision ID: 0002_evaluations
Revises: 0001_initial_schema
Create Date: 2026-09-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_evaluations"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

evaluation_status = postgresql.ENUM("PASS", "FAIL", "ERROR", name="evaluation_status", create_type=False)


def upgrade() -> None:
    postgresql.ENUM("PASS", "FAIL", "ERROR", name="evaluation_status").create(
        op.get_bind(), checkfirst=True
    )
    op.create_table(
        "evaluation_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evaluator_name", sa.String(length=160), nullable=False),
        sa.Column("score", sa.Numeric(10, 4), nullable=False),
        sa.Column("threshold", sa.Numeric(10, 4), nullable=True),
        sa.Column("status", evaluation_status, nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("label", sa.String(length=160), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["application_version_id"], ["application_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["trace_id"], ["traces.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("trace_id", "evaluator_name", name="uq_evaluation_results_trace_evaluator"),
    )
    op.create_index("ix_evaluation_results_project_id", "evaluation_results", ["project_id"])
    op.create_index(
        "ix_evaluation_results_application_version_id",
        "evaluation_results",
        ["application_version_id"],
    )
    op.create_index("ix_evaluation_results_trace_id", "evaluation_results", ["trace_id"])
    op.create_index("ix_evaluation_results_status", "evaluation_results", ["status"])
    op.create_index("ix_evaluation_results_created_at", "evaluation_results", ["created_at"])


def downgrade() -> None:
    op.drop_table("evaluation_results")
    evaluation_status.drop(op.get_bind(), checkfirst=True)
