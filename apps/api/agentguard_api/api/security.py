from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from agentguard_api.core.config import Settings, get_settings
from agentguard_api.db.session import get_session
from agentguard_api.schemas.account import (
    ApiKeyCreate,
    ApiKeyCreateResponse,
    ApiKeyRead,
    LoginRequest,
    ProviderIntegrationCreate,
    ProviderIntegrationRead,
    RedactionPolicyCreate,
    RedactionPolicyRead,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserCreate,
    UserRead,
    WorkspaceCreate,
    WorkspaceRead,
)
from agentguard_api.services.security import (
    AuthContext,
    assert_workspace_access,
    create_api_key,
    create_provider_integration,
    create_redaction_policy,
    create_user,
    create_workspace,
    get_auth_context,
    list_api_keys,
    list_provider_integrations,
    list_redaction_policies,
    list_workspaces,
    login_user,
    logout_session,
    refresh_session,
    register_user,
)

router = APIRouter(prefix="/security", tags=["security"])


@router.post("/auth/register", response_model=TokenPair, status_code=201)
async def register(
    payload: RegisterRequest,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    return await register_user(session, payload, settings)


@router.post("/auth/login", response_model=TokenPair)
async def login(
    payload: LoginRequest,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    return await login_user(session, payload, settings)


@router.post("/auth/refresh", response_model=TokenPair)
async def refresh(
    payload: RefreshRequest,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    return await refresh_session(session, payload, settings)


@router.post("/auth/logout", status_code=204)
async def logout(
    session: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
):
    await logout_session(session, auth)


@router.post("/workspaces", response_model=WorkspaceRead, status_code=201)
async def create_workspace_endpoint(
    payload: WorkspaceCreate,
    session: AsyncSession = Depends(get_session),
    _auth: AuthContext = Depends(get_auth_context),
):
    return await create_workspace(session, payload)


@router.get("/workspaces", response_model=list[WorkspaceRead])
async def read_workspaces(
    session: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
):
    return await list_workspaces(session, workspace_id=auth.workspace_id)


@router.post("/users", response_model=UserRead, status_code=201)
async def create_user_endpoint(
    payload: UserCreate,
    session: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
):
    assert_workspace_access(auth, payload.workspace_id)
    return await create_user(session, payload)


@router.post("/api-keys", response_model=ApiKeyCreateResponse, status_code=201)
async def create_api_key_endpoint(
    payload: ApiKeyCreate,
    session: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
):
    assert_workspace_access(auth, payload.workspace_id)
    raw_key, record = await create_api_key(session, payload)
    return ApiKeyCreateResponse(api_key=raw_key, record=ApiKeyRead.model_validate(record))


@router.get("/api-keys", response_model=list[ApiKeyRead])
async def read_api_keys(
    workspace_id: UUID | None = None,
    session: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
):
    if auth.workspace_id is not None:
        workspace_id = auth.workspace_id
    return await list_api_keys(session, workspace_id)


@router.post("/providers", response_model=ProviderIntegrationRead, status_code=201)
async def create_provider_endpoint(
    payload: ProviderIntegrationCreate,
    session: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
):
    assert_workspace_access(auth, payload.workspace_id)
    return await create_provider_integration(session, payload)


@router.get("/providers", response_model=list[ProviderIntegrationRead])
async def read_providers(
    workspace_id: UUID | None = None,
    session: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
):
    if auth.workspace_id is not None:
        workspace_id = auth.workspace_id
    return await list_provider_integrations(session, workspace_id)


@router.post("/redaction-policies", response_model=RedactionPolicyRead, status_code=201)
async def create_redaction_policy_endpoint(
    payload: RedactionPolicyCreate,
    session: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
):
    assert_workspace_access(auth, payload.workspace_id)
    return await create_redaction_policy(session, payload)


@router.get("/redaction-policies", response_model=list[RedactionPolicyRead])
async def read_redaction_policies(
    workspace_id: UUID | None = None,
    session: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
):
    if auth.workspace_id is not None:
        workspace_id = auth.workspace_id
    return await list_redaction_policies(session, workspace_id)
