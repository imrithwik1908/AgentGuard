from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGENTGUARD_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://agentguard:agentguard@localhost:5432/agentguard"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    auth_required: bool = False
    bootstrap_api_key: str | None = None
    access_token_minutes: int = Field(default=60, ge=1, le=24 * 60)
    refresh_token_minutes: int = Field(default=7 * 24 * 60, ge=1, le=60 * 24 * 60)
    judge_base_url: str = "https://api.openai.com/v1"
    judge_api_key: str | None = None
    judge_model: str = "gpt-4o-mini"
    judge_timeout_seconds: float = Field(default=20.0, ge=1.0, le=120.0)
    max_trace_spans: int = Field(default=500, ge=0, le=10_000)
    max_ingestion_bytes: int = Field(default=1_048_576, ge=16_384, le=50_000_000)


@lru_cache
def get_settings() -> Settings:
    return Settings()
