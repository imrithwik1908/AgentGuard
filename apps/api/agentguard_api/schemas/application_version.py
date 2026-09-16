from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApplicationVersionCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(min_length=1, max_length=200)
    version: str = Field(min_length=1, max_length=120)
    git_commit: str | None = Field(default=None, max_length=80)
    model_configuration: dict[str, Any] = Field(default_factory=dict, alias="model_config")
    prompt_config: dict[str, Any] = Field(default_factory=dict)
    retrieval_config: dict[str, Any] = Field(default_factory=dict)
    agent_config: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApplicationVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    name: str
    version: str
    git_commit: str | None
    model_configuration: dict[str, Any] = Field(
        validation_alias="model_config",
        serialization_alias="model_config",
    )
    prompt_config: dict[str, Any]
    retrieval_config: dict[str, Any]
    agent_config: dict[str, Any]
    metadata: dict[str, Any] = Field(validation_alias="meta", serialization_alias="metadata")
    created_at: datetime
