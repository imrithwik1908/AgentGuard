import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agentguard_api.core.time import utc_now
from agentguard_api.db.base import Base


class ApplicationVersion(Base):
    __tablename__ = "application_versions"
    __table_args__ = (
        UniqueConstraint("project_id", "version", name="uq_application_versions_project_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[str] = mapped_column(String(120), nullable=False)
    git_commit: Mapped[str | None] = mapped_column(String(80), nullable=True)
    model_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    prompt_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    retrieval_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    agent_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    project = relationship("Project", back_populates="versions")
    traces = relationship("Trace", back_populates="application_version")
