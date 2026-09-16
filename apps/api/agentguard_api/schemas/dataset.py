from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agentguard_api.schemas.common import TraceRead
from agentguard_api.schemas.evaluation import EvaluationRead


class DatasetCaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    input: dict[str, Any]
    expected_output: Any | None = None
    expected_substring: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_expectation(self):
        if self.expected_output is None and not self.expected_substring:
            raise ValueError("expected_output or expected_substring is required")
        return self


class DatasetCreate(BaseModel):
    project_id: UUID
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9][a-z0-9-]*$")
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    cases: list[DatasetCaseCreate] = Field(default_factory=list)


class DatasetCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dataset_id: UUID
    name: str
    input: dict[str, Any]
    expected_output: Any | None
    expected_substring: str | None
    metadata: dict[str, Any] = Field(validation_alias="meta", serialization_alias="metadata")
    created_at: datetime


class DatasetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    name: str
    slug: str
    description: str | None
    metadata: dict[str, Any] = Field(validation_alias="meta", serialization_alias="metadata")
    created_at: datetime
    cases: list[DatasetCaseRead] = []


class DatasetList(BaseModel):
    items: list[DatasetRead]
    limit: int
    offset: int
    total: int


class DatasetCaseRunCreate(BaseModel):
    application_version_id: UUID
    evaluator_name: str = Field(default="builtin.answer_contains", max_length=160)


class DatasetCaseRunRead(BaseModel):
    dataset_id: UUID
    dataset_case_id: UUID
    application_version_id: UUID
    trace: TraceRead
    evaluation: EvaluationRead


class DatasetImport(BaseModel):
    project_id: UUID
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9][a-z0-9-]*$")
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    cases: list[DatasetCaseCreate]
