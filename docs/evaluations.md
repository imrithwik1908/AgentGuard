# How AgentGuard Evaluates An AI Application

This guide explains the complete evaluation path implemented in AgentGuard v1. It covers what the
user supplies, what AgentGuard computes, how every built-in score is produced, how two versions are
paired, and how the release decision is derived.

## The Short Version

AgentGuard evaluates an AI application, not just its language model.

The application may include a prompt, model, retriever, documents, tools, routing, memory,
guardrails, and ordinary application code. A change to any of these can alter behavior. AgentGuard
records complete application runs and evaluates the stored evidence against expectations defined in
a reusable test suite.

The product flow is:

```text
Instrument -> Run -> Evaluate -> Compare -> Diagnose -> Release
```

The user defines what success means. AgentGuard executes and stores the checks, pairs the same
behavior across versions, classifies changes, and applies the release policy.

## Responsibilities

The user provides:

- the AI application;
- a project and version name;
- representative test cases;
- expected answers, requirements, sources, tools, forbidden actions, schemas, or latency budgets;
- an optional judge provider when semantic checks are required;
- optional custom evaluators for domain-specific rules.

AgentGuard provides:

- run and step instrumentation;
- whole-run trace ingestion;
- background evaluator execution;
- deterministic and LLM-based evaluators;
- score, pass/fail, explanation, evidence, and provenance persistence;
- baseline/candidate pairing;
- regression classification;
- conservative failure analysis and grouping;
- a deterministic release recommendation.

AgentGuard cannot infer a private business rule without an expectation or rubric. For example, it
cannot know that issuing a refund is correct unless the test case supplies the applicable policy,
expected action, reference answer, or another explicit requirement.

## End-To-End Evaluation Lifecycle

### 1. Register the application and versions

A **project** represents one AI application. An **application version** is a behavior snapshot such
as `prod-v1` or `candidate-v2`.

Version metadata can record observed configuration such as model/provider, prompt profile, system
prompt, retrieval `top_k`, embedding/retriever settings, tools, workflow settings, and Git commit.
These fields help explain what changed. They do not prove that a configuration change caused a
behavioral difference.

### 2. Define a reusable test suite

A **test suite** is a collection of representative behaviors. Each case contains an input and at
least one expected outcome or constraint.

```json
{
  "name": "security-access-removal",
  "input": {
    "question": "How quickly is access removed after an employee leaves?"
  },
  "expected_substring": "within four hours",
  "metadata": {
    "semantic_requirement": "State that access is removed within four hours of termination.",
    "required_sources": ["identity-access-policy"],
    "expected_tool": "lookup_security_policy",
    "forbidden_tools": ["disable_user_account"],
    "latency_budget_ms": 5000,
    "critical": true
  },
  "evaluators": [
    "builtin.semantic_correctness",
    "builtin.required_source",
    "builtin.expected_tool",
    "builtin.forbidden_tool",
    "builtin.runtime_success",
    "builtin.latency"
  ]
}
```

The `evaluators` list is optional. When omitted, AgentGuard selects applicable built-ins from the
expectations available on the case.

### 3. Run the application for both versions

The SDK records one complete application execution as a trace. Retrieval, LLM, and tool operations
are recorded as nested steps. The trace must identify the test case through `dataset_case_id` in
trace metadata or input so the worker can match evidence to the scenario.

For each case, AgentGuard needs a run from both the baseline version and the candidate version.
AgentGuard's workers analyze captured runs; they do not remotely execute arbitrary user application
code. A normal external application must produce instrumented runs before its evidence can be
scored. The included repository demos provide runners for their sample applications.

### 4. Start evaluation

When the user clicks **Evaluate candidate**, the backend creates evaluation jobs for the selected
suite, baseline, candidate, and evaluator set. The API returns without waiting for every case.

```text
QUEUED -> RUNNING -> COMPLETED | PARTIAL | FAILED
```

Each test case has its own status and retry count. A failed case does not delete successful results.
Queue identifiers are stable, completed cases are idempotent, and stale running jobs can return to
the queue after worker interruption. The web app polls until all jobs are terminal, displays 100%,
and opens the paired comparison.

### 5. Build evaluation context

For one version and test case, the worker loads the latest matching trace and extracts:

- question/input from the case;
- expected answer or semantic requirement;
- generated answer from `trace.output.answer`;
- retrieved documents from `RETRIEVER` step outputs under `documents`;
- called tools from `TOOL` step names;
- trace status and duration;
- test-case metadata and constraints.

An evaluator receives this normalized context and returns one `EvaluationResult`.

### 6. Persist result and provenance

Every result stores evaluator name/version, method, score, threshold, pass/fail status, label,
explanation, rubric, evidence, metadata, trace/test-case/version relationships, and timestamp. LLM
checks also store judge provider/model, rubric version, and prompt-template version.

This is what makes a conclusion inspectable and reproducible instead of a dashboard-only number.

### 7. Pair baseline and candidate evidence

The comparison identity is:

```text
evaluation execution/job + test case + evaluator + application version
```

For each dataset/version/evaluator combination, AgentGuard selects the latest terminal job and
follows its explicit job-case-to-result relationship. It does not average every historical result
ever generated for a case. Legacy direct results are used only when job-scoped evidence does not
exist, and their latest result is selected by timestamp.

### 8. Classify what changed

| Baseline | Candidate | Classification |
| --- | --- | --- |
| PASS | FAIL | `REGRESSED` |
| FAIL | PASS | `IMPROVED` |
| PASS | PASS | Compare score movement; otherwise `UNCHANGED` |
| FAIL | FAIL | `UNCHANGED` for binary deterministic checks |
| Missing | Any | `NOT_COMPARABLE` |

Graded LLM-judge and retrieval results support meaningful `FAIL -> FAIL` score movement. A score
change of at least `0.05` is meaningful in v1. Smaller movement is `UNCHANGED`.

### 9. Diagnose using stored evidence

For a regression, AgentGuard shows what changed, the earliest supported area of divergence, the
baseline/candidate answers, sources, tools and checks, then optional trace/provenance details.

Failure analysis describes observations and hypotheses. It does not claim causality. Correct
language is: “the candidate retrieved additional distractor documents and groundedness decreased.”
It is not: “increasing `top_k` caused the failure.”

### 10. Apply release policy

The release engine reads stored comparison evidence. It is deterministic; an LLM does not decide
whether to ship.

Policy inputs include maximum regressions, minimum candidate pass rate, allowed average paired
score drop, minimum coverage, required evaluators, runtime failures, and regressions on cases marked
`critical`.

- `PASS`: evidence is complete and all configured thresholds pass.
- `BLOCK`: at least one configured blocker is present.
- `REVIEW`: evidence is incomplete and no confirmed blocker is available.

Every decision contains explicit reasons.

## Where Each Part Runs

| Responsibility | Implemented by | What it does |
| --- | --- | --- |
| Instrumentation | Python SDK | Builds traces and concurrency-safe nested steps inside the user's process. |
| Provider capture | OpenAI-compatible SDK integration | Records model metadata, timing, token usage, responses, and provider errors without storing API keys. |
| Ingestion and validation | Async FastAPI + Pydantic | Authenticates the request, validates the complete payload, and rejects invalid parent relationships or limits. |
| Persistence | Async SQLAlchemy + PostgreSQL | Stores workspace-scoped projects, versions, traces, steps, suites, jobs, results, and provenance. |
| Job queue | Redis-compatible queue + ARQ | Separates long-running evaluation from the HTTP request and supplies stable queue job IDs. |
| Evaluation worker | Python evaluator registry | Loads trace/case evidence, runs the selected evaluator, retries case failures, and persists progress. |
| Semantic judge | Configured OpenAI-compatible provider or Ollama | Returns schema-validated rubric judgments; it never receives AgentGuard secrets or chooses the release decision. |
| Comparison | Backend comparison service | Selects the latest job-scoped results and pairs each test case/evaluator across versions. |
| Diagnosis | Backend evidence analysis + Next.js UI | Explains stored differences conservatively and exposes raw evidence only on demand. |
| Release policy | Deterministic backend policy engine | Applies explicit thresholds and returns `PASS`, `BLOCK`, or `REVIEW` with reasons. |
| Control plane | Next.js web application | Lets authenticated users configure, run, compare, investigate, and review decisions. |

All product data is scoped to an authenticated workspace in backend queries. Browser sessions are
for human users; project/workspace API keys are for SDK ingestion. API key and session-token hashes
are stored instead of reusable plaintext secrets.

## Built-In Evaluators And Exact Scores

Scores are precise decimal values from `0.0000` to `1.0000`. A high score means stronger evidence
against that evaluator's rubric. Scores from different evaluator types are normalized to the same
range but do not necessarily have identical statistical meaning.

### Deterministic answer checks

#### `builtin.exact_answer`

- Evidence: generated answer and expected answer.
- Rule: whitespace-trimmed strings must be exactly equal.
- Score: `1.0` for equality, otherwise `0.0`.
- Pass threshold: `1.0`.
- Use for stable identifiers or exact outputs where wording cannot vary.

#### `builtin.required_content`

Aliases: `builtin.answer_contains`, `required_content`.

- Evidence: generated answer and required content.
- Rule: case-insensitive substring match.
- Score: `1.0` when present, otherwise `0.0`.
- Pass threshold: `1.0`.
- This does not measure semantic equivalence.

#### `builtin.keyword_coverage`

- Evidence: generated answer and comma-separated required concepts.
- Formula: `matched required concepts / total required concepts`.
- Pass threshold: `0.8`.
- Example: 4 of 5 concepts produces `0.8` and passes.
- Matching is literal, case-insensitive substring matching.

#### `builtin.structured_output`

- Evidence: trace output and a JSON Schema in `metadata.json_schema` or
  `metadata.expected_output_schema`.
- Rule: parse string output as JSON when necessary, then validate it with JSON Schema.
- Score: `1.0` when valid, otherwise `0.0`.
- Pass threshold: `1.0`.
- An invalid user schema is a configuration error, not a model failure.

### Retrieval checks

#### `builtin.required_source`

- Evidence: document IDs from retrieval-step output and `required_sources` or
  `expected_document_ids`.
- Formula: `required document IDs found / total required document IDs`.
- Pass threshold: `1.0`; every required source must be present.
- Example: 1 of 2 required sources produces `0.5` and fails.

### Tool and agent checks

#### `builtin.expected_tool`

- Evidence: names of recorded `TOOL` steps and expected tool names.
- Formula: `expected tools called / total expected tools`.
- Pass threshold: `1.0`.

#### `builtin.forbidden_tool`

- Evidence: names of recorded `TOOL` steps and forbidden tool names.
- Score: `1.0` when no forbidden tool was called, otherwise `0.0`.
- Pass threshold: `1.0`.

These checks verify observed calls. Tool argument correctness needs a custom domain evaluator.

### Operational checks

#### `builtin.runtime_success`

- Evidence: top-level trace status.
- Score: `1.0` when status is `OK`, otherwise `0.0`.
- Pass threshold: `1.0`.

#### `builtin.latency`

- Evidence: canonical trace duration and `latency_budget_ms`.
- Score inside budget: `1.0`.
- Score over budget: `budget_ms / actual_duration_ms`.
- Pass threshold: `1.0`; a run passes only when it is within budget.

### Additional run-health checks

The **Run execution checks** action creates operational/instrumentation evidence:

- trace status: `1.0` only when the run completed;
- nested errors: `1.0` only when no step has an error;
- health latency: `min(1, budget / duration)`, with threshold `0.8`;
- inspectable evidence: steps with input/output/error divided by all steps, threshold `0.5`.

These checks answer whether a run executed and can be debugged. They do not measure answer quality.
A run can be operationally successful while failing semantic correctness.

## LLM Judge Evaluators

AI-native evaluators are used only when literal rules are insufficient and a judge provider is
configured.

### Common behavior

The judge receives a versioned rubric and structured evidence. It must return valid JSON:

```json
{
  "score": 0.86,
  "passed": true,
  "explanation": "The answer states the required timing and is consistent with the policy.",
  "evidence": ["Access is removed within four hours of termination."]
}
```

AgentGuard enforces:

- score between `0` and `1`;
- fixed v1 pass threshold of `0.8`;
- `passed` must agree with the threshold;
- output must match the structured schema;
- temperature `0`;
- one correction retry after malformed output;
- invalid output after retry fails the case instead of inventing a result;
- provider/model, rubric version, prompt version, evidence, and explanation are stored.

LLM judgments are evidence, not ground truth. They can vary across models or model versions. Combine
them with deterministic checks for important release gates.

### `builtin.semantic_correctness`

Inputs: question, expected requirement/reference, answer, and retrieved evidence.

Rubric: answer the question, remain consistent with the expected requirement, and avoid policy
details that conflict with supplied evidence.

### `builtin.groundedness`

Inputs: answer and retrieved evidence.

Rubric: material claims must be supported; absent details must not be invented; fluent but
unsupported claims lower the score.

### `builtin.retrieval_relevance`

Inputs: question, retrieved documents, and optional expected document IDs.

Rubric: documents should be relevant, distractors reduce the score, and required evidence should be
present when specified.

### `builtin.tool_selection`

Inputs: question, called tools, expected tools, and forbidden tools.

Rubric: selected actions should be appropriate, expected tools should be used, and forbidden tools
should be avoided.

## Judge Configuration And Degraded Behavior

Provider modes:

- `disabled`: deterministic evaluators only;
- `ollama`: local OpenAI-compatible Ollama endpoint;
- `openai-compatible`: external compatible endpoint with an API key.

The web app reports whether semantic judging is enabled. When disabled, candidate evaluation
continues with deterministic checks and returns a warning. It never labels a literal content check
as semantic correctness.

When a configured provider times out, rate-limits, is unreachable, or returns invalid output, the
affected case retries up to the job limit. Deterministic jobs continue. Missing required judge
evidence leads to `REVIEW` when no other blocker exists.

See [Configuration Reference](configuration.md) for environment variables.

## Aggregates, Coverage, And Score Movement

### Pass rate

```text
passing evaluation results / evaluation results in the selected evidence set
```

It is not the percentage of traces that completed unless the evidence set contains only runtime
evaluators.

### Average score

```text
sum of selected evaluation scores / number of selected evaluation results
```

Use per-evaluator rows to interpret why an average moved. A binary source check and an LLM semantic
score are both normalized to `0..1`, but represent different measurement methods.

### Comparison coverage

```text
paired comparable checks / all relevant paired-or-missing checks
```

Three comparable checks out of three is 100%. Evidence on only one side is not comparable and
lowers coverage; it is not a regression.

### Score delta

```text
candidate score - baseline score
```

A negative value means the candidate scored lower. Classification still follows pass transitions,
evaluator semantics, and the `0.05` meaningful-movement tolerance. A raw delta alone is not a
release verdict.

## Default Release Thresholds

Candidate-evaluation orchestration uses these v1 defaults:

- minimum pass rate: `0.80`;
- maximum regressions: `0`;
- allowed average paired score drop: `0.05`;
- minimum comparison coverage: `1.00`.

The release-decision endpoint accepts these values as query parameters. Its direct endpoint default
for allowed score drop is `0.00`, which is stricter. Teams should pass explicit policy values in CI
instead of relying on endpoint defaults.

A candidate is blocked by configured policy for too many paired regressions, low pass rate, excess
average score drop, runtime failures, or a regression on any `critical` case. Incomplete coverage or
missing required evaluators produces `REVIEW` when no confirmed blocker exists.

## Reading The Web App

### Test Suites

Confirm each scenario has a clear input, expected behavior, and relevant source/tool/runtime
constraints. Run the same suite against baseline and candidate.

### Evaluation progress

Progress tracks case-level background jobs. `100%` means every selected job reached a terminal
state; it does not mean every test passed.

### Releases

Read a regression in this order:

1. baseline versus candidate outcome;
2. answer, retrieval, tool/workflow, and execution strip;
3. **What changed** evidence summary;
4. side-by-side answer/source/tool evidence;
5. scoring and provenance only when needed.

### Runs

**Execution** means whether the application completed. **Behavior** means whether the output met
expectations. A green execution and failed behavior are not contradictory.

The trace waterfall is advanced debugging evidence. Green steps mean they executed successfully;
they do not mean the answer was correct.

## Trust Checklist

Before relying on a release decision, verify:

- baseline and candidate belong to the same project;
- both versions ran the same test-case IDs;
- cases represent important production behavior;
- expectations fit the selected evaluators;
- source/tool IDs match those emitted by instrumentation;
- semantic judge provider/model and rubric versions are recorded;
- comparison coverage meets policy;
- critical cases are marked explicitly;
- regressions have inspectable run evidence.

## Current V1 Boundaries

- AgentGuard evaluates captured runs; it does not execute arbitrary external application code on a
  remote user's infrastructure.
- One automatic provider integration is implemented: OpenAI-compatible chat completions.
- Tool argument correctness requires a custom evaluator.
- Failure grouping is deterministic by evaluator/stage; embedding semantic clustering is not
  implemented.
- LLM judges are fallible and are not ground truth.
- Release decisions are recommendations and CI signals, not deployment permissions.

These boundaries do not prevent the core workflow: trace application behavior, evaluate it against
declared expectations, compare the same cases, diagnose regressions, and produce an auditable
release recommendation.
