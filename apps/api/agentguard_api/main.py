import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from agentguard_api.api.ci import router as ci_router
from agentguard_api.api.datasets import router as datasets_router
from agentguard_api.api.demo import router as demo_router
from agentguard_api.api.evaluations import router as evaluations_router
from agentguard_api.api.projects import router as projects_router
from agentguard_api.api.security import router as security_router
from agentguard_api.api.traces import router as traces_router
from agentguard_api.core.config import get_settings
from agentguard_api.db.session import AsyncSessionLocal
from agentguard_api.schemas.common import ApiError
from agentguard_api.services.errors import AgentGuardError
from agentguard_api.services.evaluation_jobs import (
    claim_next_evaluation_job,
    process_evaluation_job,
    recover_stale_evaluation_jobs,
)

logger = logging.getLogger("agentguard.api")


async def run_embedded_worker() -> None:
    settings = get_settings()
    logger.info("AgentGuard embedded evaluation worker started")

    while True:
        try:
            async with AsyncSessionLocal() as session:
                await recover_stale_evaluation_jobs(
                    session,
                    stale_after_seconds=settings.worker_stale_seconds,
                )

            async with AsyncSessionLocal() as session:
                claimed = await claim_next_evaluation_job(session)

            if claimed is None:
                await asyncio.sleep(settings.worker_poll_seconds)
                continue

            job_id, workspace_id = claimed
            logger.info("Embedded worker processing evaluation job %s", job_id)
            await process_evaluation_job(
                job_id,
                settings=settings,
                workspace_id=workspace_id,
            )

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Embedded evaluation worker loop failure")
            await asyncio.sleep(settings.worker_poll_seconds)


def create_app() -> FastAPI:
    settings = get_settings()
    settings.validate_production_safety()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        embedded_worker_task: asyncio.Task | None = None
        if settings.embedded_worker_enabled:
            embedded_worker_task = asyncio.create_task(run_embedded_worker())
        try:
            yield
        finally:
            if embedded_worker_task is not None:
                embedded_worker_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await embedded_worker_task

    app = FastAPI(title="AgentGuard API", version="0.1.0", lifespan=lifespan)

    @app.middleware("http")
    async def enforce_ingestion_payload_limit(request: Request, call_next):
        if request.url.path == "/api/v1/traces" and request.method == "POST":
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > settings.max_ingestion_bytes:
                error = ApiError(
                    type="payload_too_large",
                    message="trace ingestion payload exceeds configured size limit",
                    code="payload_too_large",
                    metadata={"max_ingestion_bytes": settings.max_ingestion_bytes},
                )
                return JSONResponse(status_code=413, content=error.model_dump())
        return await call_next(request)

    @app.exception_handler(AgentGuardError)
    async def agentguard_error_handler(_request: Request, exc: AgentGuardError):
        error = ApiError(
            type=exc.__class__.__name__,
            message=exc.message,
            code=exc.code,
            metadata=exc.metadata,
        )
        return JSONResponse(status_code=exc.status_code, content=error.model_dump())

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(projects_router, prefix="/api/v1")
    app.include_router(traces_router, prefix="/api/v1")
    app.include_router(evaluations_router, prefix="/api/v1")
    app.include_router(datasets_router, prefix="/api/v1")
    app.include_router(security_router, prefix="/api/v1")
    app.include_router(ci_router, prefix="/api/v1")
    app.include_router(demo_router, prefix="/api/v1")
    return app


app = create_app()
