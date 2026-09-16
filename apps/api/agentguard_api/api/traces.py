from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from agentguard_api.core.config import Settings, get_settings
from agentguard_api.db.session import get_session
from agentguard_api.models.enums import RunStatus
from agentguard_api.schemas.common import TraceRead
from agentguard_api.schemas.trace import TraceIngest, TraceList
from agentguard_api.services.security import AuthContext, get_auth_context
from agentguard_api.services.trace_ingestion import get_trace, ingest_trace, list_traces

router = APIRouter(prefix="/traces", tags=["traces"])


@router.post("", response_model=TraceRead, status_code=201)
async def create_trace(
    payload: TraceIngest,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    auth: AuthContext = Depends(get_auth_context),
):
    return await ingest_trace(session, payload, settings, workspace_id=auth.workspace_id)


@router.get("", response_model=TraceList)
async def read_traces(
    project_id: UUID | None = None,
    application_version_id: UUID | None = None,
    status: RunStatus | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
) -> TraceList:
    traces, total = await list_traces(
        session,
        project_id=project_id,
        application_version_id=application_version_id,
        status=status.value if status else None,
        workspace_id=auth.workspace_id,
        limit=limit,
        offset=offset,
    )
    return TraceList(items=traces, limit=limit, offset=offset, total=total)


@router.get("/{trace_id}", response_model=TraceRead)
async def read_trace(
    trace_id: UUID,
    session: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
):
    return await get_trace(session, trace_id, workspace_id=auth.workspace_id)
