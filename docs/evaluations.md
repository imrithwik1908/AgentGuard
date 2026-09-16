# Evaluations

Evaluations are the evidence behind AgentGuard release decisions.

An evaluator is a check that measures whether a run behaved as expected.

## Current Evaluators

### Answer Quality

Current deterministic checks:

- Expected content: checks whether the answer contains required text.
- Exact answer match: checks whether the answer exactly matches the expected answer.
- Keyword coverage: scores whether required keywords appear in the answer.

These checks are limited but legitimate. They are useful for deterministic regression tests and smoke checks.

### Operational

Current operational checks:

- Runtime success: whether the run completed without error.
- Nested step errors: whether internal steps captured exceptions or error statuses.
- Latency budget: whether the run stayed inside a deterministic latency budget.
- Debug evidence: whether the run contains enough input/output/error data to investigate.

Operational checks are not the same as answer-quality checks. A run can be operationally healthy and still produce a bad answer.

## Planned Evaluators

These should not be presented as active until implemented.

### Semantic Correctness

Checks whether the answer means the same thing as the expected answer.

### Groundedness

Checks whether the answer is supported by retrieved evidence.

### Retrieval Relevance

Checks whether retrieved context was useful for answering the question.

### Retrieval Coverage

Checks whether required sources or documents were retrieved.

### Tool Selection

Checks whether an agent chose the expected tool or action.

### Instruction Following

Checks whether the AI application followed system, developer, and task instructions.

### Structured Output Correctness

Checks whether JSON, schemas, or tool arguments match the expected structure.

## Regression Classification

AgentGuard should compare the same behavioral test case across baseline and candidate.

It should not treat missing one-sided evidence as a regression.

Classification:

- Regressed: candidate failed or scored meaningfully worse.
- Improved: candidate passed or scored meaningfully better.
- Unchanged: no meaningful behavioral difference.
- Not comparable: missing baseline or candidate evidence.

## Release Decisions

Release decisions should be strict and understandable:

- Safe to ship: no paired regressions detected.
- Block: regressions detected: at least one paired behavioral case got worse.
- Block: runtime failures: candidate failed while running.
- Not enough evidence to decide: comparable evidence is missing.
- Not evaluated yet: no candidate evaluation evidence exists.

## Evidence Over Claims

AgentGuard should distinguish:

- observed change;
- correlated behavioral difference;
- likely explanation;
- confirmed evidence.

Do not claim causation unless a specific analysis provides causal evidence.
