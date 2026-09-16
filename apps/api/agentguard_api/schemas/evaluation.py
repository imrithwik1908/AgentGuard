from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from agentguard_api.models.enums import (
    EvaluationJobCaseStatus,
    EvaluationJobStatus,
    EvaluationMethod,
    EvaluationStatus,
)


class EvaluationCreate(BaseModel):
    trace_id: UUID
    dataset_id: UUID | None = None
    dataset_case_id: UUID | None = None
    evaluator_name: str = Field(min_length=1, max_length=160)
    evaluator_version: str = Field(default="1.0.0", min_length=1, max_length=80)
    method: EvaluationMethod = EvaluationMethod.DETERMINISTIC_BEHAVIORAL
    rubric: dict[str, Any] = Field(default_factory=dict)
    judge_model: str | None = Field(default=None, max_length=200)
    score: Decimal = Field(ge=0, le=1)
    threshold: Decimal | None = Field(default=Decimal("0.8000"), ge=0, le=1)
    status: EvaluationStatus | None = None
    passed: bool | None = None
    label: str | None = Field(default=None, max_length=160)
    explanation: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("score", "threshold")
    @classmethod
    def quantize_score(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        return value.quantize(Decimal("0.0001"))


class EvaluationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    dataset_id: UUID | None = None
    dataset_case_id: UUID | None = None
    application_version_id: UUID
    trace_id: UUID
    evaluator_name: str
    evaluator_version: str
    method: EvaluationMethod
    rubric: dict[str, Any]
    judge_model: str | None
    score: Decimal
    threshold: Decimal | None
    status: EvaluationStatus
    passed: bool
    label: str | None
    explanation: str | None
    metadata: dict[str, Any] = Field(validation_alias="meta", serialization_alias="metadata")
    created_at: datetime


class EvaluationList(BaseModel):
    items: list[EvaluationRead]
    limit: int
    offset: int
    total: int


class EvaluationSummary(BaseModel):
    project_id: UUID
    application_version_id: UUID
    evaluation_count: int
    trace_count: int
    pass_count: int
    fail_count: int
    error_count: int
    pass_rate: Decimal | None
    average_score: Decimal | None


class VersionComparison(BaseModel):
    project_id: UUID
    baseline_version_id: UUID
    candidate_version_id: UUID
    baseline: EvaluationSummary
    candidate: EvaluationSummary
    score_delta: Decimal | None
    pass_rate_delta: Decimal | None
    regression_count_delta: int


class CaseComparison(BaseModel):
    dataset_case_id: UUID | None
    evaluator_name: str
    baseline_evaluation_id: UUID | None
    candidate_evaluation_id: UUID | None
    baseline_score: Decimal | None
    candidate_score: Decimal | None
    baseline_status: EvaluationStatus | None
    candidate_status: EvaluationStatus | None
    classification: str
    explanation: str


class PairedVersionComparison(VersionComparison):
    regressed: list[CaseComparison]
    improved: list[CaseComparison]
    unchanged: list[CaseComparison]
    not_comparable: list[CaseComparison]


class ReleaseDecision(BaseModel):
    project_id: UUID
    baseline_version_id: UUID
    candidate_version_id: UUID
    decision: str
    summary: str
    reasons: list[str]
    comparison: VersionComparison
    minimum_pass_rate: Decimal
    maximum_regressions: int
    allowed_score_drop: Decimal


class EvaluationJobCreate(BaseModel):
    dataset_id: UUID
    application_version_id: UUID
    evaluator_name: str = Field(default="builtin.answer_contains", max_length=160)
    request_id: str | None = Field(default=None, max_length=120)
    max_attempts: int = Field(default=2, ge=1, le=5)


class EvaluationJobCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    dataset_case_id: UUID
    trace_id: UUID | None
    evaluation_result_id: UUID | None
    status: EvaluationJobCaseStatus
    attempts: int
    error: dict[str, Any] | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class EvaluationJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    request_id: str
    project_id: UUID
    dataset_id: UUID
    application_version_id: UUID
    evaluator_name: str
    status: EvaluationJobStatus
    total_cases: int
    completed_cases: int
    failed_cases: int
    max_attempts: int
    error: dict[str, Any] | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    cases: list[EvaluationJobCaseRead] = []
