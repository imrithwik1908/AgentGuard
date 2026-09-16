import asyncio
import logging
from uuid import UUID

from agentguard_api.core.config import get_settings
from agentguard_api.db.session import AsyncSessionLocal
from agentguard_api.services.evaluation_jobs import (
    claim_next_evaluation_job,
    process_evaluation_job,
    recover_stale_evaluation_jobs,
    redis_settings_from_url,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger("agentguard.worker")


async def process_evaluation_job_arq(
    _ctx,
    job_id: str,
    workspace_id: str | None = None,
) -> None:
    settings = get_settings()
    await process_evaluation_job(
        UUID(job_id),
        settings=settings,
        workspace_id=UUID(workspace_id) if workspace_id else None,
    )


async def run_worker() -> None:
    settings = get_settings()

    logger.info("AgentGuard evaluation worker started")

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

            logger.info(
                "Processing evaluation job %s workspace=%s",
                job_id,
                workspace_id,
            )

            try:
                await process_evaluation_job(
                    job_id,
                    settings=settings,
                    workspace_id=workspace_id,
                )
            except Exception:
                logger.exception(
                    "Evaluation job %s crashed",
                    job_id,
                )

        except Exception:
            logger.exception("Worker loop failure")
            await asyncio.sleep(settings.worker_poll_seconds)


def main() -> None:
    asyncio.run(run_worker())


settings = get_settings()
settings.validate_production_safety()


class WorkerSettings:
    functions = [process_evaluation_job_arq]
    redis_settings = redis_settings_from_url(settings.redis_url)
    max_jobs = settings.evaluation_worker_concurrency
    job_timeout = settings.evaluation_job_timeout_seconds


if __name__ == "__main__":
    main()
