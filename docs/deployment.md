# AgentGuard Deployment Guide

AgentGuard has four runtime pieces:

- Next.js web app (`apps/web`)
- FastAPI backend (`apps/api`)
- PostgreSQL database
- Redis-compatible queue for evaluation jobs

The preferred production topology is:

```text
Web -> API -> Postgres
           -> Redis queue -> worker
```

For a free public demo, `render.yaml` uses an embedded API worker instead of a separate paid
background-worker service:

```text
Web -> API + embedded evaluation worker -> Postgres
                                      -> Render Key Value
```

This keeps the product usable on free hosting, but it is still a demo-tier topology. The API service
can spin down when idle, so queued evaluations process only while the service is awake.

## Free Hosting Reality

Render currently supports free web services, free Postgres, and free Key Value instances. Render
does not provide free background-worker instances, so the blueprint enables
`AGENTGUARD_EMBEDDED_WORKER_ENABLED=true`.

Important free-tier limitations:

- free web services spin down after inactivity and wake up slowly;
- free Render Postgres expires after 30 days unless upgraded;
- free Key Value is in-memory and can lose queue state on restart;
- this is suitable for a portfolio/demo deployment, not production customer data.

## Deploy With Render Blueprint

1. Push the repository to GitHub.
2. Open Render and create a new Blueprint from this repository.
3. Select `render.yaml`.
4. Let Render create:
   - `agentguard-api`
   - `agentguard-web`
   - `agentguard-postgres`
   - `agentguard-redis`
5. Keep `AGENTGUARD_JUDGE_API_KEY` empty unless you want to enable LLM judge checks.

## Required Environment Variables

API service:

```text
AGENTGUARD_ENVIRONMENT=production
AGENTGUARD_AUTH_REQUIRED=true
AGENTGUARD_EVALUATION_QUEUE_BACKEND=redis
AGENTGUARD_EMBEDDED_WORKER_ENABLED=true
AGENTGUARD_DEMO_SEED_ENABLED=false
AGENTGUARD_DATABASE_URL=<Render Postgres connectionString>
AGENTGUARD_REDIS_URL=<Render Key Value connectionString>
```

Web service:

```text
AGENTGUARD_API_URL=<Render private hostport for agentguard-api>
```

The Blueprint fills `AGENTGUARD_API_URL` from the API service's private `hostport` value. The web
app accepts either a full URL (`https://...`) or a private hostport (`service:port`).

## Post-Deploy Smoke Test

1. Open the web URL.
2. Register a workspace.
3. Open Setup.
4. Create an SDK API key.
5. Create a project and two versions.
6. Create a test suite.
7. Run the demo or an instrumented app against both versions.
8. Start an evaluation job.
9. Confirm the job moves from `QUEUED` to `RUNNING` to `COMPLETED` or `PARTIAL`.
10. Open Releases and verify AgentGuard shows a real release state:
    - Safe to ship
    - Block: regressions detected
    - Block: runtime failures
    - Not enough evidence to decide

## Public Resume Demo Checklist

- Website is public.
- Users can register and log in.
- Workspaces isolate data.
- SDK API keys can be created from Setup.
- API accepts trace ingestion with the SDK key.
- Evaluations run asynchronously.
- Release decisions are derived from stored evaluation evidence.
- Runs expose trace/step evidence for investigation.

## When To Upgrade

Move off the free topology when real users depend on it:

- use a paid API service that does not spin down;
- run a separate paid background worker;
- use a paid Postgres database with backups;
- use a persistent Redis/Key Value plan;
- add a custom domain and monitoring.
