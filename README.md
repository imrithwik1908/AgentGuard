# AgentGuard

AgentGuard is an open-source reliability, trace, evaluation, regression-testing, and release-control platform for LLM, RAG, and agentic applications.

The current build includes the verified Phase 1 telemetry slice plus the first Phase 2A evaluation layer:

1. create a project;
2. register an application version;
3. ingest one complete nested trace atomically;
4. persist and retrieve the trace/span hierarchy;
5. prove instrumentation through a deterministic local demo agent;
6. inspect traces in the web Trace Explorer;
7. define small golden datasets for expected agent behavior;
8. run dataset cases to create fresh traces and answer-match evaluations;
9. score traces with deterministic built-in evaluators;
10. compare evaluation summaries between application versions;
11. compute a release-readiness decision from pass rate, score delta, and regressions.

Queues, persistent evaluator workers, broad replay orchestration, hosted deployment, and live third-party evaluator execution are out of scope for this checkpoint.

Production-readiness primitives now include workspaces, users, API keys, provider integration
records, dataset import/export, redaction policies, and a CI release-gate API.

## Local Setup

```bash
cp .env.example .env
docker compose up --build
```

In another shell:

```bash
cd apps/api
alembic upgrade head
```

## API

The API is served at `http://localhost:8000`.

OpenAPI docs are available at `http://localhost:8000/docs`.

The web UI is served at `http://localhost:3000`.

## Demo

Create a project and version, then run the deterministic demo agent:

```bash
curl -X POST http://localhost:8000/api/v1/projects \
  -H 'content-type: application/json' \
  -d '{"name":"Research Agent","slug":"research-agent","description":"Local deterministic demo"}'

curl -X POST http://localhost:8000/api/v1/projects/research-agent/versions \
  -H 'content-type: application/json' \
  -d '{"name":"Initial local version","version":"v1"}'

cd apps/demo-agent
export PYTHONPATH=../../packages/python-sdk
python -m demo_agent.run_demo --question "What is AgentGuard?"
python -m demo_agent.run_demo --question "please fail generation"
```

Open `http://localhost:3000/traces` and select the captured trace to inspect the waterfall. Use
the trace detail page to run the built-in status evaluator, or open
`http://localhost:3000/datasets` to create a demo golden set and run answer-match evaluations.
Then open `http://localhost:3000/evaluations` to review scores and compare versions.

For a public demo deployment, open the homepage and click **Load public demo**. That seeds a demo
project, versions, traces, a golden dataset, evaluations, and a release-board comparison so visitors
can judge the product without first wiring their own agent.

## Optional Real Model Demo

The demo agent is deterministic by default. To test it against an OpenAI-compatible chat-completions
provider:

```bash
export DEMO_AGENT_PROVIDER=openai-compatible
export DEMO_AGENT_OPENAI_API_KEY=...
export DEMO_AGENT_OPENAI_MODEL=gpt-4o-mini
python -m demo_agent.run_demo --question "What is AgentGuard?"
```

This still records the run through AgentGuard; it just swaps the local deterministic generator for a
real provider call.

## Public Launch

See `docs/public-launch-checklist.md` and `docs/deployment.md`. The repository is prepared for
public hosting, but this workspace has not deployed the website.

## Important Phase 1 Semantics

- Trace ingestion is whole-trace atomic. A trace and all supplied spans commit in one transaction, or none commit.
- `started_at` and `ended_at` are canonical. The server calculates `duration_ms`.
- Status values are constrained to `UNSET`, `OK`, and `ERROR`.
- Error values use a normalized structure with `type`, `message`, optional `stacktrace`, optional `code`, and optional metadata.
- External IDs are scoped for future idempotent ingestion: `external_trace_id` is unique within a project when present, and `external_span_id` is unique within a trace when present.
- Ingestion payload size and span count are bounded by configuration.
- Incremental and streaming span ingestion are future work.
