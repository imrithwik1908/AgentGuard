# Core Concepts

AgentGuard uses real evaluation and observability terminology, but the UI should introduce each concept at the point where it matters.

## Project

One AI application.

Examples:

- support bot;
- research agent;
- RAG question-answering system;
- tool-using workflow;
- multi-step agent.

## Version

One behavior snapshot of the application.

A version can represent changes to:

- prompt or system prompt;
- model/provider;
- retrieval strategy;
- embedding model;
- chunking;
- top-k;
- tools;
- routing logic;
- agent workflow;
- memory;
- guardrails;
- model parameters;
- application code.

## Baseline

The version you trust and compare against.

Example:

`production-v1`

## Candidate

The new version you are testing.

Example:

`candidate-v2`

## Run

One complete execution of the AI application.

Example:

One user question enters the app, the app retrieves documents, calls a model, maybe calls a tool, and returns an answer.

## Trace

The recorded sequence of important steps inside one run.

Trace is useful for debugging. It should not be the first thing a new user has to understand.

## Step

One recorded operation inside a run.

Examples:

- retrieval;
- model call;
- embedding call;
- reranking;
- tool call;
- chain step;
- custom app logic.

Internally, many observability systems call this a span. AgentGuard prefers "step" in primary UI.

## Test Suite

A set of representative cases used to check whether the AI application still behaves correctly after changes.

Internally, the backend stores these as dataset records. The user-facing concept is test suite.

## Evaluator

A check that measures whether a run behaved as expected.

Examples implemented today:

- expected answer content;
- exact answer match;
- keyword coverage;
- runtime success;
- nested step errors;
- latency budget;
- inspectable debugging evidence.

Future evaluators may include semantic correctness, groundedness, retrieval relevance, and tool-selection correctness.

## Regression

A case that worked better in the baseline than in the candidate.

This matters because an AI change can improve averages while still breaking individual behaviors that previously worked.

## Improvement

A case that became better in the candidate.

## Not Comparable

A case missing evidence from one side.

Example:

The candidate was tested, but the baseline was not. AgentGuard cannot call this a regression because there is no paired comparison.

## Release Decision

AgentGuard's evidence-backed recommendation.

Current user-facing states:

- Safe to ship.
- Block: regressions detected.
- Block: runtime failures.
- Not enough evidence to decide.
- Not evaluated yet.

## Correlation vs Causation

AgentGuard may show that a configuration change coincided with a behavioral change.

It should not claim that the configuration change caused the failure unless a specific evaluator or analysis layer provides evidence.
