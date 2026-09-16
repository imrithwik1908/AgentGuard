from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from agentguard_api.db.session import get_session
from agentguard_api.models import ApplicationVersion, Project
from agentguard_api.schemas.application_version import (
    ApplicationVersionCreate,
    ApplicationVersionRead,
)
from agentguard_api.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from agentguard_api.services.errors import AuthorizationError, ConflictError, NotFoundError
from agentguard_api.services.security import AuthContext, get_auth_context

router = APIRouter(prefix="/projects", tags=["projects"])


async def _get_project(
    session: AsyncSession,
    project_id_or_slug: str,
    workspace_id: UUID | None = None,
) -> Project:
    try:
        project_id = UUID(project_id_or_slug)
        stmt = select(Project).where(Project.id == project_id)
    except ValueError:
        stmt = select(Project).where(Project.slug == project_id_or_slug)
    if workspace_id is not None:
        stmt = stmt.where(Project.workspace_id == workspace_id)
    project = await session.scalar(stmt)
    if project is None:
        raise NotFoundError("project was not found")
    return project


@router.post("", response_model=ProjectRead, status_code=201)
async def create_project(
    payload: ProjectCreate,
    session: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
) -> Project:
    workspace_id = payload.workspace_id
    if auth.workspace_id is not None:
        if workspace_id is not None and workspace_id != auth.workspace_id:
            raise AuthorizationError("cannot create a project in another workspace")
        workspace_id = auth.workspace_id
    project = Project(
        workspace_id=workspace_id,
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
    )
    session.add(project)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("project slug already exists", metadata={"slug": payload.slug}) from exc
    await session.refresh(project)
    return project


@router.get("", response_model=list[ProjectRead])
async def list_projects(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
) -> list[Project]:
    stmt = select(Project).order_by(Project.created_at.desc()).limit(limit).offset(offset)
    if auth.workspace_id is not None:
        stmt = stmt.where(Project.workspace_id == auth.workspace_id)
    result = await session.execute(stmt)
    return list(result.scalars())


@router.get("/{project_id_or_slug}", response_model=ProjectRead)
async def read_project(
    project_id_or_slug: str,
    session: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
) -> Project:
    return await _get_project(session, project_id_or_slug, auth.workspace_id)


@router.patch("/{project_id_or_slug}", response_model=ProjectRead)
async def update_project(
    project_id_or_slug: str,
    payload: ProjectUpdate,
    session: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
) -> Project:
    project = await _get_project(session, project_id_or_slug, auth.workspace_id)
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(project, key, value)
    await session.commit()
    await session.refresh(project)
    return project


@router.post(
    "/{project_id_or_slug}/versions",
    response_model=ApplicationVersionRead,
    status_code=201,
)
async def create_application_version(
    project_id_or_slug: str,
    payload: ApplicationVersionCreate,
    session: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
) -> ApplicationVersion:
    project = await _get_project(session, project_id_or_slug, auth.workspace_id)
    version = ApplicationVersion(
        project_id=project.id,
        name=payload.name,
        version=payload.version,
        git_commit=payload.git_commit,
        model_config=payload.model_configuration,
        prompt_config=payload.prompt_config,
        retrieval_config=payload.retrieval_config,
        agent_config=payload.agent_config,
        meta=payload.metadata,
    )
    session.add(version)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError(
            "application version already exists for this project",
            metadata={"project": project_id_or_slug, "version": payload.version},
        ) from exc
    await session.refresh(version)
    return version


@router.get("/{project_id_or_slug}/versions", response_model=list[ApplicationVersionRead])
async def list_application_versions(
    project_id_or_slug: str,
    session: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
) -> list[ApplicationVersion]:
    project = await _get_project(session, project_id_or_slug, auth.workspace_id)
    result = await session.execute(
        select(ApplicationVersion)
        .where(ApplicationVersion.project_id == project.id)
        .order_by(ApplicationVersion.created_at.desc())
    )
    return list(result.scalars())
