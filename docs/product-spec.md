# AgentGuard Product Spec

AgentGuard helps teams building LLM, RAG, and agentic applications answer: did this version actually become better, what regressed, and why?

Phase 1 built the foundation for reliable trace capture. The current build also includes the first
evaluation path: stored evaluation results, golden datasets, deterministic dataset-case runs,
built-in trace-status and answer-substring evaluators, version comparison summaries, and a
deterministic release-readiness decision. It does not
implement runtime guardrails, billing, persistent evaluator workers, or hosted deployment. It now
includes local production primitives for workspaces, users, API keys, provider configuration, CI
release gates, dataset import/export, and redaction policies.

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
- Built-in deterministic trace status evaluator
- Built-in deterministic answer substring evaluator
- Evaluation browsing UI
- Dataset run UI
- Version comparison summaries
- Release-readiness decision from pass rate, score delta, and regression count
- Workspaces, users, API keys, and optional API-key enforcement
- Provider integration records for external LLM configuration
- Dataset import/export
- Redaction policies applied during trace ingestion
- CI release-gate API

## Roadmap

Future phases add hosted deployment, billing, richer evaluator workers, regression drill-downs,
counterfactual replay orchestration, and live third-party adapter execution.
