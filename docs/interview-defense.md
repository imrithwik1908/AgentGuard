# Interview Defense

## Problem

AI application teams often change prompts, retrieval logic, model settings, tools, and graph orchestration without a reliable way to inspect regressions.

## Architecture

AgentGuard owns projects, application versions, traces, and spans in PostgreSQL. The Python SDK submits whole traces to an async FastAPI API. The Next.js UI reads the API and presents projects, trace lists, and a hierarchical waterfall Trace Explorer.

## Why These Technologies

FastAPI and Pydantic provide strong API validation. SQLAlchemy 2.x and Alembic provide explicit persistence and migrations. PostgreSQL gives relational integrity plus JSONB for heterogeneous AI payloads. Next.js keeps the Phase 1 UI server-rendered where possible, reducing browser-side API/CORS complexity.

## Alternatives Considered

LangSmith, Langfuse, Phoenix, DeepEval, and RAGAS are future adapter candidates, not the core data model. Outsourcing trace ownership would weaken AgentGuard's future replay and regression capabilities.

## Current Limitations

Phase 1 has no authentication, redaction, async queue, streaming ingestion, evaluation engine, replay system, or release gates.

## Scaling Considerations

Offset pagination is acceptable for local Phase 1 workflows. Cursor/keyset pagination, ingestion queues, retention policies, and partitioning can be introduced when usage patterns justify them.
