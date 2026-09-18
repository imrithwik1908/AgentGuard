import { evaluatorInfo, numeric } from "./product-intelligence";
import type { EvaluationResult, JsonValue, Span, Trace } from "./types";

export interface ScoreExplanation {
  title: string;
  summary: string;
  calculation: string;
  expected: string[];
  observed: string[];
  missing: string[];
}

function record(value: JsonValue | Record<string, JsonValue> | null | undefined) {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, JsonValue>)
    : {};
}

function strings(value: JsonValue | undefined): string[] {
  return Array.isArray(value) ? value.map(String) : [];
}

function text(value: JsonValue | undefined): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function percent(value: string | number | null | undefined): string {
  const parsed = numeric(value);
  return parsed === null ? "not available" : `${Math.round(parsed * 100)}%`;
}

export function explainEvaluation(evaluation: EvaluationResult): ScoreExplanation {
  const rubric = record(evaluation.rubric);
  const metadata = record(evaluation.metadata);
  const name = evaluation.evaluator_name;
  const score = numeric(evaluation.score) ?? 0;

  if (name === "builtin.answer_contains" || name === "builtin.required_content") {
    const requirement =
      text(rubric.requirement) ??
      text(rubric.expected_substring) ??
      text(metadata.expected) ??
      text(metadata.expected_substring);
    const answer = text(metadata.answer);
    return {
      title: "Required content",
      summary: evaluation.passed
        ? "The required content appeared in the generated answer."
        : "The required content was not found in the generated answer.",
      calculation: "Case-insensitive required-content match: found = 100%; missing = 0%. All required content must be present.",
      expected: requirement ? [requirement] : [],
      observed: answer ? [answer] : [],
      missing: !evaluation.passed && requirement ? [requirement] : []
    };
  }

  if (name === "builtin.answer_exact" || name === "builtin.exact_answer") {
    const expected = text(rubric.expected_answer) ?? text(metadata.expected) ?? text(metadata.expected_answer);
    const answer = text(metadata.answer);
    return {
      title: "Exact answer",
      summary: evaluation.passed ? "The normalized answer exactly matched the expected answer." : "The answer did not exactly match the expected answer.",
      calculation: "Normalized exact equality: equal = 100%; different = 0%.",
      expected: expected ? [expected] : [],
      observed: answer ? [answer] : [],
      missing: !evaluation.passed && expected ? [expected] : []
    };
  }

  if (name === "builtin.structured_output") {
    const validationError = text(metadata.validation_error);
    return {
      title: "Structured output",
      summary: validationError ? `Schema validation failed: ${validationError}` : "The output is valid JSON and matches the configured schema.",
      calculation: "Valid JSON that satisfies the entire configured schema = 100%; otherwise 0%.",
      expected: ["Valid output matching the configured JSON schema"],
      observed: validationError ? [validationError] : ["Schema matched"],
      missing: validationError ? ["Schema compliance"] : []
    };
  }

  if (name === "builtin.keyword_coverage") {
    const expected = strings(rubric.keywords).length
      ? strings(rubric.keywords)
      : strings(metadata.keywords);
    const observed = strings(metadata.matched_keywords);
    const missing = expected.filter((item) => !observed.includes(item));
    return {
      title: "Required concepts",
      summary: `${observed.length} of ${expected.length} required concepts appeared explicitly in the answer.`,
      calculation: `${observed.length} found / ${expected.length} required = ${percent(score)}; pass at ${percent(evaluation.threshold)}.`,
      expected,
      observed,
      missing
    };
  }

  if (name === "builtin.required_source") {
    const expected = strings(rubric.expected_document_ids);
    const observed = strings(metadata.retrieved_document_ids);
    const matched = strings(metadata.matched_document_ids);
    return {
      title: "Required sources",
      summary: `${matched.length} of ${expected.length} required sources were retrieved.`,
      calculation: `${matched.length} found / ${expected.length} required = ${percent(score)}; every required source must be present.`,
      expected,
      observed,
      missing: expected.filter((item) => !matched.includes(item))
    };
  }

  if (name === "builtin.expected_tool") {
    const expected = strings(rubric.expected_tools);
    const observed = strings(metadata.called_tools);
    const matched = strings(metadata.matched_tools);
    return {
      title: "Expected tools",
      summary: matched.length === expected.length ? "Every expected tool was called." : "An expected tool was not called.",
      calculation: `${matched.length} observed / ${expected.length} expected = ${percent(score)}.`,
      expected,
      observed,
      missing: expected.filter((item) => !matched.includes(item))
    };
  }

  if (name === "builtin.forbidden_tool") {
    const expected = strings(rubric.forbidden_tools);
    const observed = strings(metadata.called_tools);
    const violations = strings(metadata.violations);
    return {
      title: "Forbidden tools",
      summary: violations.length ? `${violations.length} prohibited tool call(s) were observed.` : "No prohibited tool was called.",
      calculation: violations.length ? "Any prohibited call makes this check fail." : "No violations = 100%.",
      expected: expected.map((item) => `Avoid ${item}`),
      observed,
      missing: violations
    };
  }

  if (name.includes("latency")) {
    const duration = Number(metadata.duration_ms ?? 0);
    const budget = Number(metadata.latency_budget_ms ?? rubric.latency_budget_ms ?? 0);
    return {
      title: "Latency budget",
      summary: duration <= budget ? `Completed within the ${budget} ms budget.` : `Took ${duration} ms, above the ${budget} ms budget.`,
      calculation: duration <= budget ? "Within budget = 100%." : `${budget} ms budget / ${duration} ms observed = ${percent(score)}.`,
      expected: budget ? [`At most ${budget} ms`] : [],
      observed: duration ? [`${duration} ms`] : [],
      missing: []
    };
  }

  if (name.includes("runtime") || name === "builtin.trace_health.status") {
    const status = text(metadata.trace_status) ?? "unknown";
    return {
      title: "Execution completed",
      summary: evaluation.passed ? "The application finished without a top-level runtime error." : `The application ended with status ${status}.`,
      calculation: "Completed successfully = 100%; runtime error = 0%.",
      expected: ["Run status OK"],
      observed: [`Run status ${status}`],
      missing: []
    };
  }

  if (name === "builtin.trace_health.error_spans") {
    const count = Number(metadata.error_span_count ?? 0);
    return {
      title: "Internal step errors",
      summary: count === 0 ? "No recorded step captured an exception." : `${count} step(s) captured an exception.`,
      calculation: "No errored steps = 100%; one or more = 0%.",
      expected: ["No step errors"],
      observed: [`${count} step error(s)`],
      missing: []
    };
  }

  if (name === "builtin.trace_health.evidence") {
    const spanCount = Number(metadata.span_count ?? 0);
    const evidenceCount = Number(metadata.evidence_span_count ?? 0);
    return {
      title: "Debug evidence",
      summary: `${evidenceCount} of ${spanCount} recorded steps contain input, output, or error evidence.`,
      calculation: `${evidenceCount} inspectable / ${spanCount} total = ${percent(score)}; pass at 50%.`,
      expected: ["At least half of steps are inspectable"],
      observed: [`${evidenceCount} of ${spanCount} steps`],
      missing: []
    };
  }

  const judgeEvidence = strings(metadata.judge_evidence);
  return {
    title: evaluatorInfo(name).name,
    summary: evaluation.explanation ?? evaluatorInfo(name).description,
    calculation: `Stored score ${percent(score)}; pass at ${percent(evaluation.threshold)}.`,
    expected: [],
    observed: judgeEvidence,
    missing: []
  };
}

export function evaluationReliability(evaluation: EvaluationResult): string {
  if (evaluation.method === "LLM_JUDGE") {
    return `Rubric-based model judgment${evaluation.judge_model ? ` by ${evaluation.judge_model}` : ""}. Useful for semantic behavior, but not ground truth; inspect its evidence and rubric.`;
  }
  if (evaluation.method === "INSTRUMENTATION_ONLY") {
    return "Measures whether debugging evidence was recorded. It does not measure answer quality.";
  }
  return "Deterministic and repeatable for the same stored evidence. Its accuracy is limited to the explicit rule; it does not infer unstated meaning.";
}

export function traceAnswer(trace: Trace | null): string | null {
  if (!trace) return null;
  const output = record(trace.output);
  const direct = text(output.answer);
  if (direct) return direct;
  const llm = [...trace.spans].reverse().find((span) => span.type === "LLM");
  return llm ? text(record(llm.output).answer) : null;
}

export function retrievalIds(trace: Trace | null): string[] {
  if (!trace) return [];
  const direct = strings(record(trace.output).retrieved_document_ids);
  if (direct.length) return direct;
  const ids = new Set<string>();
  for (const span of trace.spans.filter((item) => item.type === "RETRIEVER")) {
    const documents = record(span.output).documents;
    if (!Array.isArray(documents)) continue;
    for (const document of documents) {
      const id = text(record(document).id);
      if (id) ids.add(id);
    }
  }
  return [...ids];
}

export function toolNames(trace: Trace | null): string[] {
  if (!trace) return [];
  return trace.spans.filter((span) => span.type === "TOOL").map((span) => span.name);
}

export function systemPrompt(trace: Trace | null): string | null {
  const llm = trace?.spans.find((span) => span.type === "LLM");
  const messages = llm ? record(llm.input).messages : null;
  if (!Array.isArray(messages)) return null;
  const system = messages.find((message) => record(message).role === "system");
  return system ? text(record(system).content) : null;
}

export function observedRuntimeChanges(baseline: Trace | null, candidate: Trace | null) {
  const changes: Array<{ label: string; field: string; before: string; after: string }> = [];
  const baselineMeta = record(baseline?.metadata);
  const candidateMeta = record(candidate?.metadata);
  for (const [field, label] of [
    ["retrieval_top_k", "Retrieval configuration"],
    ["model", "Model configuration"],
    ["provider", "Model configuration"]
  ] as const) {
    const before = baselineMeta[field];
    const after = candidateMeta[field];
    if (before !== undefined && after !== undefined && JSON.stringify(before) !== JSON.stringify(after)) {
      changes.push({ label, field, before: String(before), after: String(after) });
    }
  }
  const beforePrompt = systemPrompt(baseline);
  const afterPrompt = systemPrompt(candidate);
  if (beforePrompt && afterPrompt && beforePrompt !== afterPrompt) {
    changes.push({ label: "Prompt configuration", field: "system_prompt", before: beforePrompt, after: afterPrompt });
  }
  return changes;
}

export function spanEvidenceSummary(span: Span): string[] {
  if (span.type === "RETRIEVER") {
    const documents = record(span.output).documents;
    return Array.isArray(documents)
      ? documents.map((document) => text(record(document).id) ?? text(record(document).title) ?? "Retrieved document")
      : [];
  }
  if (span.type === "TOOL") return [span.name];
  if (span.type === "LLM") {
    const answer = text(record(span.output).answer);
    return answer ? [answer] : [];
  }
  return [];
}
