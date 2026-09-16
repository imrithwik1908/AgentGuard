# Troubleshooting

## The Web App Shows "AgentGuard API Is Unreachable"

Cause:

The Next.js frontend cannot reach the FastAPI backend.

Check:

```bash
curl http://127.0.0.1:8000/healthz
```

Expected:

```json
{"status":"ok"}
```

If it fails, start the backend:

```bash
cd apps/api
AGENTGUARD_DATABASE_URL=postgresql+asyncpg://agentguard:agentguard@localhost:55432/agentguard \
uv run --project . uvicorn agentguard_api.main:app --host 127.0.0.1 --port 8000
```

## The SDK Runs But No Runs Appear In The UI

Check:

- `base_url` points to the backend, not the frontend.
- Project slug exists.
- Version exists for that project.
- SDK submission did not log `agentguard_trace_submission_failed`.

Example:

```python
AgentGuard(
    base_url="http://127.0.0.1:8000",
    project="support-agent",
    version="candidate-v2",
)
```

## `project was not found`

Create the project in **Setup** first.

The SDK does not create projects automatically because project/version creation is a product-control-plane action.

## `application version was not found`

Register the version in **Setup** before sending telemetry.

## A Candidate Shows "Not Enough Evidence"

This is not a bug.

AgentGuard needs the same behavioral test case evaluated in both baseline and candidate.

Fix:

Run the test suite against both versions.

## A Case Is "Not Comparable"

Meaning:

One side is missing evidence.

Examples:

- baseline was evaluated but candidate was not;
- candidate was evaluated but baseline was not;
- evaluation lacks `dataset_case_id`;
- the two runs are not tied to the same test case.

## Candidate Has Runtime Failures

Open **Runs**, select the failed run, then expand **View execution details**.

Look for:

- failed step;
- exception type;
- stacktrace;
- input/output around the failure.

## PyPI Upload Fails Because The Name Is Taken

The plain `agentguard` package name is not available for this project.

Use:

```bash
agentguard-reliability
```

Import still remains:

```python
from agentguard import AgentGuard
```

## PyPI Upload Fails Because The Version Already Exists

PyPI does not allow replacing uploaded files for the same version.

Increment the version in:

```text
packages/python-sdk/pyproject.toml
```

Then rebuild and upload.

## Docker Is Not Running

If Docker Desktop is unavailable, run PostgreSQL locally and point the backend at it.

Current local development fallback used in this project:

```bash
postgres://agentguard:agentguard@localhost:55432/agentguard
```

SQLAlchemy async URL:

```bash
postgresql+asyncpg://agentguard:agentguard@localhost:55432/agentguard
```
