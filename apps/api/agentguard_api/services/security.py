import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from agentguard_api.core.config import Settings, get_settings
from agentguard_api.core.time import utc_now
from agentguard_api.db.session import get_session
from agentguard_api.models import (
    ApiKey,
    AuthSession,
    ProviderIntegration,
    RedactionPolicy,
    User,
    Workspace,
)
from agentguard_api.schemas.account import (
    ApiKeyCreate,
    LoginRequest,
    ProviderIntegrationCreate,
    RedactionPolicyCreate,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserCreate,
    WorkspaceCreate,
    WorkspaceRead,
)
from agentguard_api.services.errors import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)


@dataclass(frozen=True)
class AuthContext:
    workspace_id: UUID | None
    api_key_id: UUID | None
    user_id: UUID | None = None
    session_id: UUID | None = None


def hash_api_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hash_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 210_000)
    return f"pbkdf2_sha256$210000${salt}${digest.hex()}"


def _verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        algorithm, iterations_raw, salt, expected = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations_raw),
        ).hex()
        return hmac.compare_digest(digest, expected)
    except (ValueError, TypeError):
        return False


def _new_token() -> str:
    return secrets.token_urlsafe(48)


async def _issue_session_tokens(
    session: AsyncSession,
    *,
    user: User,
    settings: Settings,
) -> TokenPair:
    access_token = _new_token()
    refresh_token = _new_token()
    now = utc_now()
    expires_at = now + timedelta(minutes=settings.access_token_minutes)
    refresh_expires_at = now + timedelta(minutes=settings.refresh_token_minutes)
    auth_session = AuthSession(
        user_id=user.id,
        workspace_id=user.workspace_id,
        access_token_hash=_hash_token(access_token),
        refresh_token_hash=_hash_token(refresh_token),
        expires_at=expires_at,
        refresh_expires_at=refresh_expires_at,
    )
    session.add(auth_session)
    await session.commit()
    await session.refresh(user, attribute_names=["workspace"])
    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
        refresh_expires_at=refresh_expires_at,
        user=user,
        workspace=WorkspaceRead.model_validate(user.workspace),
    )


async def register_user(
    session: AsyncSession,
    payload: RegisterRequest,
    settings: Settings,
) -> TokenPair:
    workspace = Workspace(name=payload.workspace_name, slug=payload.workspace_slug)
    user = User(
        workspace=workspace,
        email=payload.email.lower(),
        name=payload.name,
        role="owner",
        password_hash=_hash_password(payload.password),
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError(
            "workspace slug or user already exists",
            metadata={"workspace_slug": payload.workspace_slug, "email": payload.email},
        ) from exc
    return await _issue_session_tokens(session, user=user, settings=settings)


async def login_user(
    session: AsyncSession,
    payload: LoginRequest,
    settings: Settings,
) -> TokenPair:
    stmt = select(User).join(Workspace).where(User.email == payload.email.lower())
    if payload.workspace_slug:
        stmt = stmt.where(Workspace.slug == payload.workspace_slug)
    result = await session.execute(stmt)
    users = list(result.scalars())
    if len(users) != 1 or not _verify_password(payload.password, users[0].password_hash):
        raise AuthenticationError("invalid email, workspace, or password")
    return await _issue_session_tokens(session, user=users[0], settings=settings)


async def refresh_session(
    session: AsyncSession,
    payload: RefreshRequest,
    settings: Settings,
) -> TokenPair:
    result = await session.execute(
        select(AuthSession)
        .join(User, User.id == AuthSession.user_id)
        .where(AuthSession.refresh_token_hash == _hash_token(payload.refresh_token))
    )
    auth_session = result.scalar_one_or_none()
    now = utc_now()
    if (
        auth_session is None
        or auth_session.revoked_at is not None
        or auth_session.refresh_expires_at <= now
    ):
        raise AuthenticationError("refresh token is invalid or expired")
    user = await session.get(User, auth_session.user_id)
    if user is None:
        raise AuthenticationError("refresh token is invalid or expired")
    auth_session.revoked_at = now
    return await _issue_session_tokens(session, user=user, settings=settings)


async def logout_session(session: AsyncSession, context: AuthContext) -> None:
    if context.session_id is None:
        return
    auth_session = await session.get(AuthSession, context.session_id)
    if auth_session is None:
        return
    auth_session.revoked_at = utc_now()
    await session.commit()


async def create_workspace(session: AsyncSession, payload: WorkspaceCreate) -> Workspace:
    workspace = Workspace(name=payload.name, slug=payload.slug)
    session.add(workspace)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError(
            "workspace slug already exists",
            metadata={"slug": payload.slug},
        ) from exc
    await session.refresh(workspace)
    return workspace


async def list_workspaces(
    session: AsyncSession, workspace_id: UUID | None = None
) -> list[Workspace]:
    stmt = select(Workspace).order_by(Workspace.created_at.desc())
    if workspace_id is not None:
        stmt = stmt.where(Workspace.id == workspace_id)
    result = await session.execute(stmt)
    return list(result.scalars())


async def create_user(session: AsyncSession, payload: UserCreate) -> User:
    if await session.get(Workspace, payload.workspace_id) is None:
        raise NotFoundError(
            "workspace was not found",
            metadata={"workspace_id": str(payload.workspace_id)},
        )
    user = User(
        workspace_id=payload.workspace_id,
        email=payload.email.lower(),
        name=payload.name,
        password_hash=_hash_password(payload.password) if payload.password else None,
        role=payload.role,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError(
            "user already exists in workspace",
            metadata={"email": payload.email},
        ) from exc
    await session.refresh(user)
    return user


async def create_api_key(session: AsyncSession, payload: ApiKeyCreate) -> tuple[str, ApiKey]:
    if await session.get(Workspace, payload.workspace_id) is None:
        raise NotFoundError(
            "workspace was not found",
            metadata={"workspace_id": str(payload.workspace_id)},
        )
    raw_key = f"ag_{secrets.token_urlsafe(32)}"
    record = ApiKey(
        workspace_id=payload.workspace_id,
        name=payload.name,
        prefix=raw_key[:12],
        key_hash=hash_api_key(raw_key),
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return raw_key, record


async def authenticate_api_key(session: AsyncSession, raw_key: str) -> AuthContext:
    key_hash = hash_api_key(raw_key)
    result = await session.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True))
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise AuthenticationError("invalid or inactive AgentGuard API key")
    record.last_used_at = utc_now()
    await session.commit()
    return AuthContext(workspace_id=record.workspace_id, api_key_id=record.id)


async def authenticate_access_token(session: AsyncSession, raw_token: str) -> AuthContext:
    result = await session.execute(
        select(AuthSession).where(
            AuthSession.access_token_hash == _hash_token(raw_token),
            AuthSession.revoked_at.is_(None),
        )
    )
    auth_session = result.scalar_one_or_none()
    if auth_session is None or auth_session.expires_at <= utc_now():
        raise AuthenticationError("access token is invalid or expired")
    return AuthContext(
        workspace_id=auth_session.workspace_id,
        api_key_id=None,
        user_id=auth_session.user_id,
        session_id=auth_session.id,
    )


async def get_auth_context(
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> AuthContext:
    api_key = request.headers.get("x-agentguard-api-key")
    if api_key:
        if settings.bootstrap_api_key and api_key == settings.bootstrap_api_key:
            return AuthContext(workspace_id=None, api_key_id=None)
        return await authenticate_api_key(session, api_key)

    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and token:
        return await authenticate_access_token(session, token)

    if settings.auth_required:
        raise AuthenticationError("authentication is required")
    return AuthContext(workspace_id=None, api_key_id=None)


def assert_workspace_access(context: AuthContext, workspace_id: UUID | None) -> None:
    if context.workspace_id is None or workspace_id is None:
        return
    if context.workspace_id != workspace_id:
        raise AuthorizationError("resource belongs to a different workspace")


async def create_provider_integration(
    session: AsyncSession, payload: ProviderIntegrationCreate
) -> ProviderIntegration:
    if await session.get(Workspace, payload.workspace_id) is None:
        raise NotFoundError(
            "workspace was not found",
            metadata={"workspace_id": str(payload.workspace_id)},
        )
    integration = ProviderIntegration(**payload.model_dump())
    session.add(integration)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError(
            "provider integration already exists",
            metadata={"provider": payload.provider, "name": payload.name},
        ) from exc
    await session.refresh(integration)
    return integration


async def list_provider_integrations(
    session: AsyncSession, workspace_id: UUID | None
) -> list[ProviderIntegration]:
    stmt = select(ProviderIntegration).order_by(ProviderIntegration.created_at.desc())
    if workspace_id:
        stmt = stmt.where(ProviderIntegration.workspace_id == workspace_id)
    result = await session.execute(stmt)
    return list(result.scalars())


async def create_redaction_policy(
    session: AsyncSession, payload: RedactionPolicyCreate
) -> RedactionPolicy:
    if await session.get(Workspace, payload.workspace_id) is None:
        raise NotFoundError(
            "workspace was not found",
            metadata={"workspace_id": str(payload.workspace_id)},
        )
    if payload.mode not in {"mask", "drop"}:
        raise ValidationError("redaction policy mode must be mask or drop")
    policy = RedactionPolicy(**payload.model_dump())
    session.add(policy)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError(
            "redaction policy already exists",
            metadata={"name": payload.name},
        ) from exc
    await session.refresh(policy)
    return policy


async def list_redaction_policies(
    session: AsyncSession, workspace_id: UUID | None
) -> list[RedactionPolicy]:
    stmt = select(RedactionPolicy).order_by(RedactionPolicy.created_at.desc())
    if workspace_id:
        stmt = stmt.where(RedactionPolicy.workspace_id == workspace_id)
    result = await session.execute(stmt)
    return list(result.scalars())
