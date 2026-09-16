from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9][a-z0-9-]*$")


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    created_at: datetime


class RegisterRequest(BaseModel):
    workspace_name: str = Field(min_length=1, max_length=200)
    workspace_slug: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9][a-z0-9-]*$")
    email: str = Field(min_length=3, max_length=320)
    name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=8, max_length=200)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=200)
    workspace_slug: str | None = Field(default=None, max_length=120)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=500)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_at: datetime
    refresh_expires_at: datetime
    user: "UserRead"
    workspace: WorkspaceRead


class UserCreate(BaseModel):
    workspace_id: UUID
    email: str = Field(min_length=3, max_length=320)
    name: str = Field(min_length=1, max_length=200)
    password: str | None = Field(default=None, min_length=8, max_length=200)
    role: str = Field(default="owner", max_length=40)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    email: str
    name: str
    role: str
    created_at: datetime


class ApiKeyCreate(BaseModel):
    workspace_id: UUID
    name: str = Field(min_length=1, max_length=200)


class ApiKeyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    name: str
    prefix: str
    is_active: bool
    last_used_at: datetime | None
    created_at: datetime


class ApiKeyCreateResponse(BaseModel):
    api_key: str
    record: ApiKeyRead


class ProviderIntegrationCreate(BaseModel):
    workspace_id: UUID
    provider: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    default_model: str | None = Field(default=None, max_length=160)
    base_url: str | None = Field(default=None, max_length=500)
    api_key_secret_ref: str | None = Field(default=None, max_length=240)
    is_enabled: bool = True


class ProviderIntegrationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    provider: str
    name: str
    default_model: str | None
    base_url: str | None
    api_key_secret_ref: str | None
    is_enabled: bool
    created_at: datetime


class RedactionPolicyCreate(BaseModel):
    workspace_id: UUID
    name: str = Field(min_length=1, max_length=160)
    mode: str = Field(default="mask", max_length=40)
    patterns: str = ""
    is_enabled: bool = True


class RedactionPolicyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    name: str
    mode: str
    patterns: str
    is_enabled: bool
    created_at: datetime
