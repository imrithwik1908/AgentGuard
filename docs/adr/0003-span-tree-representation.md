# ADR 0003: Span Tree Representation

## Status

Accepted

## Decision

Represent span hierarchy with an adjacency list: each span may reference a nullable `parent_span_id`.

## Consequences

This supports zero or more root spans per trace and arbitrary nested descendants. Nested sets and materialized paths are unnecessary for Phase 1.

