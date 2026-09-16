"""Initial AgentGuard schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-09-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

trace_status = postgresql.ENUM("UNSET", "OK", "ERROR", name="trace_status", create_type=False)
span_status = postgresql.ENUM("UNSET", "OK", "ERROR", name="span_status", create_type=False)
span_type = postgresql.ENUM(
    "AGENT",
    "LLM",
    "RETRIEVER",
    "TOOL",
    "CHAIN",
    "EMBEDDING",
    "RERANKER",
    "CUSTOM",
    name="span_type",
    create_type=False,
)


def upgrade() -> None:
    postgresql.ENUM("UNSET", "OK", "ERROR", name="trace_status").create(op.get_bind(), checkfirst=True)
    postgresql.ENUM("UNSET", "OK", "ERROR", name="span_status").create(op.get_bind(), checkfirst=True)
    postgresql.ENUM(
        "AGENT",
        "LLM",
        "RETRIEVER",
        "TOOL",
        "CHAIN",
        "EMBEDDING",
        "RERANKER",
        "CUSTOM",
        name="span_type",
    ).create(op.get_bind(), checkfirst=True)

    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("slug", name="uq_projects_slug"),
    )

    op.create_table(
        "application_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("version", sa.String(length=120), nullable=False),
        sa.Column("git_commit", sa.String(length=80), nullable=True),
        sa.Column("model_config", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("prompt_config", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("retrieval_config", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("agent_config", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", "version", name="uq_application_versions_project_version"),
    )
    op.create_index("ix_application_versions_project_id", "application_versions", ["project_id"])

    op.create_table(
        "traces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_trace_id", sa.String(length=200), nullable=True),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("status", trace_status, nullable=False),
        sa.Column("input", postgresql.JSONB(), nullable=True),
        sa.Column("output", postgresql.JSONB(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("total_input_tokens", sa.Integer(), nullable=True),
        sa.Column("total_output_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost", sa.Numeric(18, 8), nullable=True),
        sa.Column("error", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["application_version_id"], ["application_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_traces_project_id", "traces", ["project_id"])
    op.create_index("ix_traces_application_version_id", "traces", ["application_version_id"])
    op.create_index("ix_traces_created_at", "traces", ["created_at"])
    op.create_index("ix_traces_status", "traces", ["status"])
    op.create_index(
        "uq_traces_project_external_trace_id",
        "traces",
        ["project_id", "external_trace_id"],
        unique=True,
        postgresql_where=sa.text("external_trace_id IS NOT NULL"),
    )

    op.create_table(
        "spans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_span_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("external_span_id", sa.String(length=200), nullable=True),
        sa.Column("type", span_type, nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("status", span_status, nullable=False),
        sa.Column("input", postgresql.JSONB(), nullable=True),
        sa.Column("output", postgresql.JSONB(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("attributes", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("provider", sa.String(length=120), nullable=True),
        sa.Column("model_name", sa.String(length=200), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost", sa.Numeric(18, 8), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("error", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["parent_span_id"], ["spans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["trace_id"], ["traces.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_spans_trace_id", "spans", ["trace_id"])
    op.create_index("ix_spans_parent_span_id", "spans", ["parent_span_id"])
    op.create_index(
        "uq_spans_trace_external_span_id",
        "spans",
        ["trace_id", "external_span_id"],
        unique=True,
        postgresql_where=sa.text("external_span_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_table("spans")
    op.drop_table("traces")
    op.drop_table("application_versions")
    op.drop_table("projects")
    span_type.drop(op.get_bind(), checkfirst=True)
    span_status.drop(op.get_bind(), checkfirst=True)
    trace_status.drop(op.get_bind(), checkfirst=True)
