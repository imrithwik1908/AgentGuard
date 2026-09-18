# AgentGuard Product Spec

AgentGuard helps teams building LLM, RAG, and agentic applications answer: did this version actually become better, what regressed, and why?

AgentGuard v1 combines reliable trace capture with declarative test suites, background evaluator
workers, deterministic and optional AI-based checks, job-scoped paired comparison, failure evidence,
and deterministic release decisions. It also includes workspaces, users, hashed API keys, provider
configuration, CI release gates, dataset import/export, and ingestion redaction policies.

## Intended Users

AgentGuard is for engineers shipping AI systems whose behavior changes when prompts, models, retrieval logic, tools, or orchestration graphs change.

## Implemented Scope

- Projects
- Application versions
- Whole-trace atomic ingestion
- Nested span persistence
- Python SDK instrumentation
- Deterministic demo agent
- Trace retrieval APIs
- Project and trace browsing UI
- Hierarchical waterfall Trace Explorer
- Stored evaluation results
- Golden datasets and dataset cases
- Built-in deterministic answer, retrieval, tool, schema, runtime, and latency evaluators
- Rubric-based semantic correctness, groundedness, retrieval relevance, and tool-selection judges
- Redis/ARQ background jobs with per-case progress and retries
- Evaluation browsing UI
- Dataset run UI
- Version comparison summaries
- Job-scoped paired regression classification and evidence coverage
- Release decision from explicit policy thresholds and stored evidence
- Workspaces, users, API keys, and optional API-key enforcement
- Provider integration records for external LLM configuration
- Dataset import/export
- Redaction policies applied during trace ingestion
- CI release-gate API

## Roadmap

Future work includes semantic failure clustering, more framework/provider adapters, counterfactual
replay, organization-level RBAC, billing, and enterprise scaling.
