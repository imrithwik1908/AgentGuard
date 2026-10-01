# API Reference

This reference describes the current AgentGuard HTTP API implemented by the FastAPI backend.

Base URL for local development:

```text
http://127.0.0.1:8000
```

All product APIs are under:

```text
/api/v1
```

## Health

### `GET /healthz`

Checks whether the backend process is running.

Response:

```json
{
  "status": "ok"
}
```

## Projects

Projects represent AI applications.

### `POST /api/v1/projects`

Create a project.

Request:

```json
{
  "name": "Support Agent",
  "slug": "support-agent",
  "description": "Customer-support AI application"
}
```

### `GET /api/v1/projects`

List projects.

Query parameters:

- `limit`: default `50`, max `200`.
- `offset`: default `0`.

### `GET /api/v1/projects/{project_id_or_slug}`

Fetch a project by UUID or slug.

### `PATCH /api/v1/projects/{project_id_or_slug}`

Update project fields.

## Versions

Versions represent behavior snapshots of an AI application.

### `POST /api/v1/projects/{project_id_or_slug}/versions`

Create an application version.

Request:

```json
{
  "name": "Candidate prompt",
  "version": "candidate-v2",
  "git_commit": null,
  "model_configuration": {},
  "prompt_config": {},
  "retrieval_config": {},
  "agent_config": {},
  "metadata": {}
}
```

### `GET /api/v1/projects/{project_id_or_slug}/versions`

List versions for one project.

## Runs / Traces

The backend stores runs as traces with nested spans.

### `POST /api/v1/traces`

Ingest one complete run and all supplied steps atomically.

The SDK calls this endpoint automatically.

Important behavior:

- The trace and spans are persisted in one database transaction.
- If validation or insertion fails, none of the trace is committed.
- `external_trace_id` is unique within a project when non-null.
- `external_span_id` is unique within a trace when non-null.

### `GET /api/v1/traces`

List runs.

Query parameters:

- `project_id`
- `application_version_id`
- `status`
- `limit`
- `offset`

### `GET /api/v1/traces/{trace_id}`

Fetch one run with its nested steps.

## Evaluations

Evaluations are checks that measure whether a run behaved as expected.

### `POST /api/v1/evaluations`

Create an evaluation result for a run.

Request:

```json
{
  "trace_id": "uuid",
  "dataset_id": "uuid",
  "dataset_case_id": "uuid",
  "evaluator_name": "builtin.answer_contains",
  "score": "1.0000",
  "threshold": "1.0000",
  "passed": true,
  "label": "Expected answer content found",
  "explanation": "Checks whether the answer contains required text.",
  "metadata": {
    "expected_substring": "not returnable"
  }
}
```

### `GET /api/v1/evaluations`

List evaluation results.

Query parameters:

- `project_id`
- `application_version_id`
- `trace_id`
- `limit`
- `offset`

### `POST /api/v1/evaluations/traces/{trace_id}/status-check`

Create a built-in runtime-status check.

### `POST /api/v1/evaluations/traces/{trace_id}/health-check`

Create built-in operational checks:

- run completed;
- nested step errors;
- latency budget;
- inspectable debugging evidence.

### `GET /api/v1/evaluations/summary/{application_version_id}`

Summarize evaluation results for one version.

### `GET /api/v1/evaluations/compare`

Compare aggregate evaluation statistics between two versions.

Query parameters:

- `baseline_version_id`
- `candidate_version_id`

Aggregate statistics summarize the latest selected evidence. Use the paired comparison endpoint for
regression classification because it pairs the same test case and evaluator across versions.

### `GET /api/v1/evaluations/release-decision`

Return the current backend release-decision object.

The backend release engine derives its decision from paired case/evaluator evidence, comparison
coverage, pass rate, score movement, runtime failures, critical cases, and configured policy.

### `GET /api/v1/evaluations/compare/paired`

Pair the same test case and evaluator across baseline and candidate. Results are classified as
`REGRESSED`, `IMPROVED`, `UNCHANGED`, or `NOT_COMPARABLE` using the latest terminal job-scoped
evidence.

### `POST /api/v1/evaluations/orchestrate`

Create background jobs for the selected test suite, baseline, candidate, and evaluator set. The
response includes job records, judge capability flags, and warnings when semantic judging was
requested but is unavailable.

### `GET /api/v1/evaluations/capabilities`

Report whether AI judges are configured, plus the active judge provider/model and available
semantic evaluator names. This endpoint requires browser authentication.

See [How AgentGuard Evaluates An AI Application](evaluations.md) for exact scoring and pairing
semantics.

## Test Suites

The backend currently stores test suites as datasets.

### `POST /api/v1/datasets`

Create a test suite with cases.

### `GET /api/v1/datasets`

List test suites.

### `GET /api/v1/datasets/{dataset_id}`

Fetch one test suite.

### `POST /api/v1/datasets/{dataset_id}/cases`

Add a case to a test suite.

### `POST /api/v1/datasets/cases/{case_id}/run`

Run one dataset case against a version using the built-in deterministic demo runner.

## Security And Integrations

Current endpoints exist for:

- workspaces;
- users;
- API keys;
- provider integrations;
- redaction policies.

These are early platform primitives, not a complete production auth/billing layer.

## CI

### `GET /api/v1/ci/release-gate`

Return release-gate style information for CI usage.

This is intended for future automation around pull requests and deployments.
