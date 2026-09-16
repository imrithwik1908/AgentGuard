"""Add workspaces, API keys, provider integrations, and redaction policies.

Revision ID: 0004_security_integrations
Revises: 0003_datasets
Create Date: 2026-09-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_security_integrations"
down_revision: str | None = "0003_datasets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("slug", name="uq_workspaces_slug"),
    )
    op.create_index("ix_workspaces_created_at", "workspaces", ["created_at"])

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("workspace_id", "email", name="uq_users_workspace_email"),
    )
    op.create_index("ix_users_workspace_id", "users", ["workspace_id"])

    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("prefix", sa.String(length=16), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("key_hash", name="uq_api_keys_key_hash"),
    )
    op.create_index("ix_api_keys_workspace_id", "api_keys", ["workspace_id"])
    op.create_index("ix_api_keys_prefix", "api_keys", ["prefix"])

    op.create_table(
        "provider_integrations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("default_model", sa.String(length=160), nullable=True),
        sa.Column("base_url", sa.String(length=500), nullable=True),
        sa.Column("api_key_secret_ref", sa.String(length=240), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("workspace_id", "provider", "name", name="uq_provider_integrations_name"),
    )
    op.create_index("ix_provider_integrations_workspace_id", "provider_integrations", ["workspace_id"])

    op.create_table(
        "redaction_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("mode", sa.String(length=40), nullable=False),
        sa.Column("patterns", sa.Text(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("workspace_id", "name", name="uq_redaction_policies_name"),
    )
    op.create_index("ix_redaction_policies_workspace_id", "redaction_policies", ["workspace_id"])

    op.add_column("projects", sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_projects_workspace_id",
        "projects",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_projects_workspace_id", "projects", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_projects_workspace_id", table_name="projects")
    op.drop_constraint("fk_projects_workspace_id", "projects", type_="foreignkey")
    op.drop_column("projects", "workspace_id")
    op.drop_table("redaction_policies")
    op.drop_table("provider_integrations")
    op.drop_table("api_keys")
    op.drop_table("users")
    op.drop_table("workspaces")
