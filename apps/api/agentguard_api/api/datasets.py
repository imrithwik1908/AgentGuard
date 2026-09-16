from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from agentguard_api.core.config import Settings, get_settings
from agentguard_api.db.session import get_session
from agentguard_api.schemas.dataset import (
    DatasetCaseCreate,
    DatasetCaseRead,
    DatasetCaseRunCreate,
    DatasetCaseRunRead,
    DatasetCreate,
    DatasetImport,
    DatasetList,
    DatasetRead,
)
from agentguard_api.services.datasets import (
    create_dataset,
    create_dataset_case,
    get_dataset,
    import_dataset,
    list_datasets,
    run_dataset_case,
)
from agentguard_api.services.security import AuthContext, get_auth_context

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.post("", response_model=DatasetRead, status_code=201)
async def create_dataset_endpoint(
    payload: DatasetCreate,
    session: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
):
    return await create_dataset(session, payload, workspace_id=auth.workspace_id)


@router.get("", response_model=DatasetList)
async def read_datasets(
    project_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
) -> DatasetList:
    datasets, total = await list_datasets(
        session,
        project_id=project_id,
        workspace_id=auth.workspace_id,
        limit=limit,
        offset=offset,
    )
    return DatasetList(items=datasets, limit=limit, offset=offset, total=total)


@router.get("/{dataset_id}", response_model=DatasetRead)
async def read_dataset(
    dataset_id: UUID,
    session: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
):
    return await get_dataset(session, dataset_id, workspace_id=auth.workspace_id)


@router.get("/{dataset_id}/export", response_model=DatasetRead)
async def export_dataset(
    dataset_id: UUID,
    session: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
):
    return await get_dataset(session, dataset_id, workspace_id=auth.workspace_id)


@router.post("/import", response_model=DatasetRead, status_code=201)
async def import_dataset_endpoint(
    payload: DatasetImport,
    session: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
):
    return await import_dataset(session, payload, workspace_id=auth.workspace_id)


@router.post("/{dataset_id}/cases", response_model=DatasetCaseRead, status_code=201)
async def create_case(
    dataset_id: UUID,
    payload: DatasetCaseCreate,
    session: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
):
    return await create_dataset_case(session, dataset_id, payload, workspace_id=auth.workspace_id)


@router.post("/cases/{case_id}/run", response_model=DatasetCaseRunRead, status_code=201)
async def run_case(
    case_id: UUID,
    payload: DatasetCaseRunCreate,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    auth: AuthContext = Depends(get_auth_context),
) -> DatasetCaseRunRead:
    trace, evaluation = await run_dataset_case(
        session,
        case_id=case_id,
        application_version_id=payload.application_version_id,
        evaluator_name=payload.evaluator_name,
        settings=settings,
        workspace_id=auth.workspace_id,
    )
    return DatasetCaseRunRead(
        dataset_id=evaluation.dataset_id,
        dataset_case_id=case_id,
        application_version_id=payload.application_version_id,
        trace=trace,
        evaluation=evaluation,
    )
