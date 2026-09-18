from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AGENTGUARD_",
        env_file=".env",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://agentguard:agentguard@localhost:5432/agentguard"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    environment: Literal["local", "test", "production"] = "local"

    # Authentication can remain false for unit/local tests.
    # Deployment docker-compose explicitly turns this on.
    auth_required: bool = False
    bootstrap_api_key: str | None = None

    access_token_minutes: int = Field(default=60, ge=1, le=24 * 60)
    refresh_token_minutes: int = Field(
        default=7 * 24 * 60,
        ge=1,
        le=60 * 24 * 60,
    )

    # LLM-as-a-judge
    judge_provider: Literal["disabled", "ollama", "openai-compatible"] = "disabled"
    judge_base_url: str = "https://api.openai.com/v1"
    judge_api_key: str | None = None
    judge_model: str = "gpt-4o-mini"
    judge_timeout_seconds: float = Field(
        default=20.0,
        ge=1.0,
        le=120.0,
    )

    # Trace safety
    max_trace_spans: int = Field(default=500, ge=0, le=10_000)
    max_ingestion_bytes: int = Field(
        default=1_048_576,
        ge=16_384,
        le=50_000_000,
    )

    # Evaluation jobs. Local/test may use the database-polling fallback; hosted
    # production must enqueue work through Redis so API processes do not execute
    # long-running evaluations.
    evaluation_queue_backend: Literal["inline", "redis"] = "inline"
    redis_url: str = "redis://localhost:6379/0"
    evaluation_job_timeout_seconds: int = Field(default=300, ge=10, le=3600)
    evaluation_worker_concurrency: int = Field(default=4, ge=1, le=64)

    # Single-process worker for local or zero-cost preview deployments.
    embedded_worker_enabled: bool = False
    worker_poll_seconds: float = Field(default=1.0, ge=0.1, le=30.0)
    worker_stale_seconds: int = Field(default=300, ge=30, le=3600)

    # Regression semantics
    deterministic_score_tolerance: float = Field(default=0.05, ge=0, le=1)
    llm_judge_score_tolerance: float = Field(default=0.05, ge=0, le=1)

    # Authenticated demo data is opt-in for each deployment.
    demo_seed_enabled: bool = False

    @model_validator(mode="after")
    def normalize_database_url(self) -> "Settings":
        if self.database_url.startswith("postgres://"):
            self.database_url = self.database_url.replace(
                "postgres://",
                "postgresql+asyncpg://",
                1,
            )
        elif self.database_url.startswith("postgresql://"):
            self.database_url = self.database_url.replace(
                "postgresql://",
                "postgresql+asyncpg://",
                1,
            )
        return self

    @property
    def judge_enabled(self) -> bool:
        if self.judge_provider == "ollama":
            return True
        if self.judge_provider == "openai-compatible":
            return bool(self.judge_api_key)
        return False

    def validate_production_safety(self) -> None:
        if self.environment != "production":
            return
        if not self.auth_required:
            raise RuntimeError("AGENTGUARD_AUTH_REQUIRED=true is required in production")
        if self.evaluation_queue_backend != "redis":
            raise RuntimeError(
                "AGENTGUARD_EVALUATION_QUEUE_BACKEND=redis is required in production"
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
