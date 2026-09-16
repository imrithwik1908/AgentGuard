"""Add stable queue job id for evaluation jobs.

Revision ID: 0007_eval_queue_job
Revises: 0006_eval_jobs
Create Date: 2026-09-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_eval_queue_job"
down_revision: str | None = "0006_eval_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "evaluation_jobs",
        sa.Column("queue_job_id", sa.String(length=200), nullable=True),
    )
    op.create_index(
        "ix_evaluation_jobs_queue_job_id",
        "evaluation_jobs",
        ["queue_job_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_evaluation_jobs_queue_job_id", table_name="evaluation_jobs")
    op.drop_column("evaluation_jobs", "queue_job_id")
