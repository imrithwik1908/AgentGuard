# Evaluations

An evaluator is a versioned check that turns stored run evidence into a score, pass/fail result, and
explanation. Users define expected behavior; AgentGuard executes the checks.

## Built-In Registry

| Evaluator | Category | Method | Required evidence |
| --- | --- | --- | --- |
| `builtin.exact_answer` | Answer quality | Deterministic behavioral | Expected answer and generated answer |
| `builtin.required_content` | Answer quality | Deterministic behavioral | Required text and generated answer |
| `builtin.structured_output` | Answer quality | Deterministic behavioral | JSON Schema and output |
| `builtin.keyword_coverage` | Answer quality | Deterministic behavioral | Required keywords and output |
| `builtin.required_source` | Retrieval | Deterministic retrieval | Required source IDs and retrieval steps |
| `builtin.expected_tool` | Agent behavior | Deterministic behavioral | Expected tool and tool steps |
| `builtin.forbidden_tool` | Agent behavior | Deterministic behavioral | Forbidden tools and tool steps |
| `builtin.runtime_success` | Operational | Deterministic operational | Trace status |
| `builtin.latency` | Operational | Deterministic operational | Trace duration and budget |
| `builtin.semantic_correctness` | Answer quality | LLM judge | Question, expectation, answer, evidence |
| `builtin.groundedness` | Answer quality | LLM judge | Answer and retrieved evidence |
| `builtin.retrieval_relevance` | Retrieval | LLM judge | Question and retrieved evidence |
| `builtin.tool_selection` | Agent behavior | LLM judge | Called/expected/forbidden tools |

Trace-health checks are operational/instrumentation evidence. They are never labeled as answer
quality.

## Provenance

Every result stores evaluator name/version, method, rubric/config, judge model when applicable,
threshold, score, pass/fail, explanation, metadata/evidence, and timestamp. AI metadata additionally
stores judge provider, rubric version, and prompt-template version.

The fixed v1 AI threshold is `0.80`. Judge output is validated as structured JSON, including that
the returned pass flag agrees with the score threshold.

## Provider Modes

- `disabled`: deterministic evaluators only.
- `ollama`: local OpenAI-compatible Ollama endpoint; no API key required.
- `openai-compatible`: external compatible endpoint; API key required.

If the judge is unavailable, the affected job case records a structured error and retries up to its
configured limit. Other cases and deterministic jobs continue. Missing evaluator evidence prevents
an automatic `PASS` when that evaluator is required by release policy.

## Comparison Semantics

The comparison unit is one terminal evaluation execution/job + test case + evaluator + version.
For each dataset/version/evaluator, AgentGuard selects the latest terminal job and follows its
explicit job-case-to-result relationship. Direct legacy results use the latest timestamp only when
no job-scoped evidence exists.

- `PASS -> FAIL`: `REGRESSED`
- `FAIL -> PASS`: `IMPROVED`
- equivalent deterministic `FAIL -> FAIL`: `UNCHANGED`
- meaningful graded score decrease: `REGRESSED`
- score movement inside configured tolerance: `UNCHANGED`
- missing side: `NOT_COMPARABLE`

Comparison coverage is `comparable paired checks / total relevant paired checks`.

## Failure Analysis

V1 groups failures deterministically by evaluator and observed stage. The stored summary separates
observation from hypotheses and includes a causality disclaimer. The optional structured judge
adapter can produce conservative failure-analysis summaries, but it cannot modify evaluator rows or
release policy.

Semantic embedding clustering is future work.

## Release Policy

The policy engine is deterministic. Inputs include maximum regressions, minimum pass rate, allowed
score drop, minimum coverage, required evaluator names, runtime failures, and critical test cases.

- `PASS`: evidence is complete and all thresholds pass.
- `BLOCK`: one or more configured blockers are present.
- `REVIEW`: evidence is incomplete without a confirmed blocker.

Reasons are returned with every decision so CI and the UI can explain the result.
