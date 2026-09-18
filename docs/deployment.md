# Deployment

## Production Topology

```text
Browser -> Next.js web -> FastAPI API + embedded worker -> PostgreSQL
                                  |
                                  +-> Redis/Key Value
                                  |
                                  +-> optional judge provider
```

[`render.yaml`](../render.yaml) defines the zero-cost portfolio topology: web, API, PostgreSQL, and
Redis. The API enqueues evaluation jobs and returns `202`; an embedded background worker claims the
persisted jobs and records per-case progress plus terminal `COMPLETED`, `PARTIAL`, or `FAILED`
status. A paid deployment should move the same worker loop into a dedicated worker service.

## Render Blueprint

1. Push the repository to GitHub.
2. In Render, create a Blueprint from `render.yaml`.
3. Review the resource plans before applying it.
4. Set `AGENTGUARD_JUDGE_API_KEY` only when using an external provider.
5. Verify `/healthz`, registration, SDK-key ingestion, a queued evaluation, and a release comparison.

The API is the single migration owner and runs `alembic upgrade head` before serving traffic. The
free Render preview runs its background worker in the API process. Docker Compose keeps the worker
as a separate service so local development exercises the production-style process boundary.

## Required Production Settings

```text
AGENTGUARD_ENVIRONMENT=production
AGENTGUARD_AUTH_REQUIRED=true
AGENTGUARD_EVALUATION_QUEUE_BACKEND=redis
AGENTGUARD_EMBEDDED_WORKER_ENABLED=true
AGENTGUARD_DEMO_SEED_ENABLED=true
AGENTGUARD_DATABASE_URL=<managed PostgreSQL URL>
AGENTGUARD_REDIS_URL=<managed Redis/Key Value URL>
```

Production startup refuses disabled auth or inline evaluation execution.

For external AI judging:

```text
AGENTGUARD_JUDGE_PROVIDER=openai-compatible
AGENTGUARD_JUDGE_BASE_URL=https://provider.example/v1
AGENTGUARD_JUDGE_MODEL=<model>
AGENTGUARD_JUDGE_API_KEY=<secret>
```

Do not expose judge/provider secrets through `NEXT_PUBLIC_*` variables.

## Local Ollama

Use `http://localhost:11434` for a natively running API and
`http://host.docker.internal:11434` for Docker. The compose file supplies the host mapping.

A public Render worker cannot reach an Ollama process on a developer laptop without a deliberately
configured secure network tunnel. The public demo should remain deterministic-only unless a
reachable judge is provided.

## Zero-Cost Reality

Render does not offer a free dedicated background-worker instance. This repository therefore uses
the API's embedded worker for the public zero-cost portfolio preview. Work pauses when the free API
sleeps and resumes after it wakes; PostgreSQL remains the source of truth for job progress.

For sustained production traffic, set `AGENTGUARD_EMBEDDED_WORKER_ENABLED=false` and run
`arq agentguard_api.worker.WorkerSettings` as a dedicated worker connected to the same PostgreSQL
and Redis services. Free database lifetimes and Redis persistence may also be limited by Render's
current plans. These limits must not be presented as production-grade guarantees.

## Local Full Stack

```bash
cp .env.example .env
docker compose up --build
```

If local ports are occupied:

```bash
AGENTGUARD_POSTGRES_PORT=55432 AGENTGUARD_REDIS_PORT=56379 docker compose up --build
```

Internal container networking remains `postgres:5432` and `redis:6379`.

## Smoke Test

1. Register and log in.
2. Create an SDK key in Setup.
3. Create a project and `prod-v1` / `candidate-v2`.
4. Run the same suite against both versions.
5. Click **Evaluate candidate** and observe worker progress.
6. Open Releases and inspect regression evidence plus policy reasons.
7. Open a candidate run and distinguish execution health from behavioral evaluation.

## Operations

- Keep PostgreSQL backups and Redis persistence appropriate to the environment.
- Monitor API/worker logs and failed job cases.
- Rotate SDK keys; only hashes are stored.
- Use HTTPS and private service networking.
- Keep `AGENTGUARD_DEMO_SEED_ENABLED=false` unless an authenticated demo is intentional.
