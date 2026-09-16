# Configuration Reference

This page lists the configuration values used by AgentGuard.

## Backend Environment Variables

Prefix: `AGENTGUARD_`

### `AGENTGUARD_DATABASE_URL`

SQLAlchemy async database URL.

Local example:

```bash
AGENTGUARD_DATABASE_URL=postgresql+asyncpg://agentguard:agentguard@localhost:55432/agentguard
```

Docker example:

```bash
AGENTGUARD_DATABASE_URL=postgresql+asyncpg://agentguard:agentguard@postgres:5432/agentguard
```

### `AGENTGUARD_API_HOST`

Host for the API server.

Local default:

```bash
AGENTGUARD_API_HOST=0.0.0.0
```

### `AGENTGUARD_API_PORT`

API port.

Default:

```bash
AGENTGUARD_API_PORT=8000
```

### `AGENTGUARD_AUTH_REQUIRED`

Whether API key auth is required for `/api/v1` routes.

Default:

```bash
AGENTGUARD_AUTH_REQUIRED=false
```

### `AGENTGUARD_BOOTSTRAP_API_KEY`

Optional bootstrap API key accepted when auth is enabled.

### `AGENTGUARD_MAX_TRACE_SPANS`

Maximum number of spans/steps accepted per ingested trace.

Default:

```bash
AGENTGUARD_MAX_TRACE_SPANS=500
```

### `AGENTGUARD_MAX_INGESTION_BYTES`

Maximum accepted trace ingestion payload size.

Default:

```bash
AGENTGUARD_MAX_INGESTION_BYTES=1048576
```

## Web Environment Variables

### `AGENTGUARD_API_URL`

Server-side API URL used by Next.js.

Local example:

```bash
AGENTGUARD_API_URL=http://127.0.0.1:8000
```

Docker example:

```bash
AGENTGUARD_API_URL=http://api:8000
```

### `NEXT_PUBLIC_AGENTGUARD_API_URL`

Browser-visible fallback API URL.

Local example:

```bash
NEXT_PUBLIC_AGENTGUARD_API_URL=http://127.0.0.1:8000
```

## SDK Configuration

```python
client = AgentGuard(
    base_url="http://127.0.0.1:8000",
    project="support-agent",
    version="candidate-v2",
    api_key=None,
    raise_on_failure=False,
    timeout_seconds=5.0,
)
```

### `base_url`

AgentGuard API URL.

### `project`

Project slug.

The project must already exist in AgentGuard.

### `version`

Application version string.

The version must already exist for the project.

### `api_key`

Optional API key.

Required only when backend authentication is enabled.

### `raise_on_failure`

Default:

```python
False
```

When false, telemetry submission failures log a structured warning and do not crash the instrumented application.

### `timeout_seconds`

HTTP submission timeout for SDK ingestion.

## Local Development Stack

Temporary local stack used during development:

- PostgreSQL: `localhost:55432`
- API: `http://127.0.0.1:8000`
- Web: `http://localhost:3000`

Docker Compose stack:

```bash
docker compose up --build
```

Docker services:

- `postgres`
- `api`
- `web`
