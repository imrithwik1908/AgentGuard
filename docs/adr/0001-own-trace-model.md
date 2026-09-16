# ADR 0001: AgentGuard Owns Its Trace Model

## Status

Accepted

## Decision

AgentGuard stores first-class project, version, trace, and span entities instead of outsourcing trace persistence to an external observability platform.

## Consequences

This gives AgentGuard a stable foundation for evaluation, regression analysis, and counterfactual replay. It also requires us to implement ingestion validation, storage, and retrieval carefully from the beginning.

