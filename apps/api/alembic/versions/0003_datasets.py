"""Add datasets and dataset case evaluation links.

Revision ID: 0003_datasets
Revises: 0002_evaluations
Create Date: 2026-09-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_datasets"
down_revision: str | None = "0002_evaluations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "datasets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", "slug", name="uq_datasets_project_slug"),
    )
    op.create_index("ix_datasets_project_id", "datasets", ["project_id"])
    op.create_index("ix_datasets_created_at", "datasets", ["created_at"])

    op.create_table(
        "dataset_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("input", postgresql.JSONB(), nullable=False),
        sa.Column("expected_output", postgresql.JSONB(none_as_null=True), nullable=True),
        sa.Column("expected_substring", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("dataset_id", "name", name="uq_dataset_cases_dataset_name"),
    )
    op.create_index("ix_dataset_cases_dataset_id", "dataset_cases", ["dataset_id"])
    op.create_index("ix_dataset_cases_created_at", "dataset_cases", ["created_at"])

    op.add_column("evaluation_results", sa.Column("dataset_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column(
        "evaluation_results",
        sa.Column("dataset_case_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_evaluation_results_dataset_id",
        "evaluation_results",
        "datasets",
        ["dataset_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_evaluation_results_dataset_case_id",
        "evaluation_results",
        "dataset_cases",
        ["dataset_case_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_evaluation_results_dataset_id", "evaluation_results", ["dataset_id"])
    op.create_index(
        "ix_evaluation_results_dataset_case_id",
        "evaluation_results",
        ["dataset_case_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_evaluation_results_dataset_case_id", table_name="evaluation_results")
    op.drop_index("ix_evaluation_results_dataset_id", table_name="evaluation_results")
    op.drop_constraint("fk_evaluation_results_dataset_case_id", "evaluation_results", type_="foreignkey")
    op.drop_constraint("fk_evaluation_results_dataset_id", "evaluation_results", type_="foreignkey")
    op.drop_column("evaluation_results", "dataset_case_id")
    op.drop_column("evaluation_results", "dataset_id")
    op.drop_table("dataset_cases")
    op.drop_table("datasets")
