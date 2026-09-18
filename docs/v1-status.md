# AgentGuard v1 Status

## Supported

- Authenticated users, workspaces, hashed SDK keys, and workspace-scoped resources.
- Async FastAPI/SQLAlchemy with PostgreSQL and whole-trace atomic ingestion.
- Python SDK trace/span API plus `trace_run`, `llm_call`, `retrieval`, and `tool` helpers.
- OpenAI-compatible chat-completions instrumentation.
- Declarative test suites and a built-in evaluator registry.
- Deterministic, local-Ollama, and external OpenAI-compatible judge modes.
- Redis/ARQ jobs with per-case progress, retries, result reuse, partial status, stale-job recovery,
  and configurable timeout/concurrency.
- Job-scoped paired comparison, deterministic failure grouping, and auditable release policy.
- Next.js setup, suites, progress, releases, evidence, and trace investigation workflow.
- Thirty-case customer-support RAG reference application.

## Verification

The exact tests and workflows executed during the sealing pass are recorded in the final task report.
PostgreSQL integration tests must run with `AGENTGUARD_TEST_DATABASE_URL`; a skipped suite is not
accepted as verification.

Ollama/OpenAI-compatible protocol and schema validation are automated without downloading a model.
A real local-model run is recorded separately when the operator has installed a suitable model.

## Limitations

- A real local judge requires the operator to install Ollama and choose a model for their hardware.
- Public cloud demo deployments default to deterministic evaluators unless a judge is reachable.
- Failure grouping is deterministic, not embedding-based semantic clustering.
- OpenAI-compatible chat completions is the only automatic provider integration in v1.
- The SDK has no persistent client retry queue.
- This is a portfolio/research-grade platform, not an enterprise observability replacement.

## Frozen Follow-Up Scope

Semantic failure clustering, more integrations, replay/counterfactual testing, organization-level
RBAC, generated clients, and enterprise scaling are future work.
