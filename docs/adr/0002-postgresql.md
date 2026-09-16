# ADR 0002: PostgreSQL Persistence

## Status

Accepted

## Decision

Use PostgreSQL with JSONB for Phase 1 persistence.

## Consequences

Relational constraints protect ownership and topology. JSONB fields keep heterogeneous AI payloads flexible without premature normalization. PostgreSQL also supports partial unique indexes needed for scoped external identifiers.

