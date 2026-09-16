# Public Launch Checklist

This is the practical bar for showing AgentGuard publicly as a serious student project.

## Must Be True

- The web app is reachable from a public URL.
- The API is reachable from the web app's server environment.
- PostgreSQL is hosted with migrations applied through `alembic upgrade head`.
- Visitors can click **Load public demo** and see a populated release board.
- The guide page explains:
  - what a trace is;
  - what a span is;
  - what datasets/evaluations are;
  - how a release decision is produced;
  - what is real today vs future work.
- The README explains SDK usage and optional API-key auth.
- No raw provider secrets are stored in the database.
- Auth can be enabled with `AGENTGUARD_AUTH_REQUIRED=true`.

## Honest Product Claims

AgentGuard currently promises:

- whole-trace ingestion;
- nested span visualization;
- Python SDK instrumentation;
- golden dataset runs;
- deterministic built-in evaluators;
- version comparison;
- CI release-gate API;
- redaction policies during ingestion;
- provider integration configuration.

AgentGuard does **not** yet promise:

- hosted multi-tenant SaaS operations;
- billing;
- production support guarantees;
- background evaluator workers;
- live third-party judge execution by default.

## Suggested Hosting Shape

- PostgreSQL: Neon, Supabase, Railway, Render Postgres, or any managed PostgreSQL.
- API: Render/Railway/Fly.io container running `apps/api`.
- Web: Vercel/Render/Railway running `apps/web`.
- Environment:
  - API gets `AGENTGUARD_DATABASE_URL`.
  - Web gets `AGENTGUARD_API_URL=https://your-api-host`.
  - Browser-visible URL, if needed, gets `NEXT_PUBLIC_AGENTGUARD_API_URL=https://your-api-host`.

Do not deploy from this checklist until the project owner explicitly chooses the host.
