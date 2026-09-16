# ADR 0004: Synchronous Whole-Trace Ingestion

## Status

Accepted

## Decision

Phase 1 uses synchronous whole-trace atomic ingestion. The API persists the trace and all spans in one transaction.

## Consequences

This keeps local development and acceptance testing straightforward. Incremental/streaming ingestion and durable retry queues are future work.

