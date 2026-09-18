"""Scope project slugs to their workspace.

Revision ID: 0008_scope_project_slugs
Revises: 0007_eval_queue_job
Create Date: 2026-09-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008_scope_project_slugs"
down_revision: str | None = "0007_eval_queue_job"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_projects_slug", "projects", type_="unique")
    op.create_unique_constraint(
        "uq_projects_workspace_slug",
        "projects",
        ["workspace_id", "slug"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_projects_workspace_slug", "projects", type_="unique")
    op.create_unique_constraint("uq_projects_slug", "projects", ["slug"])
