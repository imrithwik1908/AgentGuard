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

function quoted(values: string[]): string {
  if (!values.length) return "the configured requirement";
  return values.map((value) => `“${value}”`).join(values.length > 2 ? ", " : " and ");
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

export function evaluationExpectation(evaluation: EvaluationResult): string {
  const reasoning = explainEvaluation(evaluation);
  const threshold = numeric(evaluation.threshold) ?? 1;

  if (evaluation.evaluator_name === "builtin.keyword_coverage") {
    const requiredCount = Math.max(1, Math.ceil(reasoning.expected.length * threshold));
    return `The answer must explicitly include at least ${requiredCount} of ${reasoning.expected.length} configured words or phrases: ${quoted(reasoning.expected)}.`;
  }
  if (
    evaluation.evaluator_name === "builtin.answer_contains" ||
    evaluation.evaluator_name === "builtin.required_content"
  ) {
    return `The answer must explicitly include the configured requirement: ${quoted(reasoning.expected)}.`;
  }
  if (
    evaluation.evaluator_name === "builtin.answer_exact" ||
    evaluation.evaluator_name === "builtin.exact_answer"
  ) {
    return `The normalized answer must exactly match: ${quoted(reasoning.expected)}.`;
  }
  if (evaluation.evaluator_name === "builtin.required_source") {
    return `The run must retrieve every required source: ${quoted(reasoning.expected)}.`;
  }
  if (evaluation.evaluator_name === "builtin.expected_tool") {
    return `The application must call every expected tool: ${quoted(reasoning.expected)}.`;
  }
  if (evaluation.evaluator_name === "builtin.forbidden_tool") {
    return `The application must avoid the prohibited tools configured for this scenario.`;
  }
  if (evaluation.evaluator_name.includes("latency")) {
    return reasoning.expected.length
      ? `The complete run must finish within ${reasoning.expected[0].replace("At most ", "")}.`
      : "The complete run must stay within the configured latency budget.";
  }
  if (
    evaluation.evaluator_name.includes("runtime") ||
    evaluation.evaluator_name.includes("trace_health.status")
  ) {
    return "The application must complete without a top-level runtime error.";
  }
  if (evaluation.method === "LLM_JUDGE") {
    return "The answer must satisfy the stored semantic rubric for this scenario.";
  }
  return reasoning.expected.length
    ? `The run must satisfy: ${quoted(reasoning.expected)}.`
    : "The run must satisfy the check configured for this scenario.";
}

export function evaluationObservation(evaluation: EvaluationResult): string {
  const reasoning = explainEvaluation(evaluation);

  if (evaluation.evaluator_name === "builtin.keyword_coverage") {
    const found = reasoning.observed.length
      ? `It explicitly contained ${quoted(reasoning.observed)}`
      : "It contained none of the configured words or phrases";
    const missing = reasoning.missing.length
      ? ` It did not explicitly contain ${quoted(reasoning.missing)}.`
      : ".";
    return `${found}.${missing}`.replace("..", ".");
  }
  if (
    evaluation.evaluator_name === "builtin.answer_contains" ||
    evaluation.evaluator_name === "builtin.required_content"
  ) {
    return evaluation.passed
      ? "The configured text was found explicitly in the recorded answer."
      : `The recorded answer did not explicitly contain ${quoted(reasoning.missing)}.`;
  }
  if (evaluation.evaluator_name === "builtin.required_source") {
    return reasoning.observed.length
      ? `The run retrieved ${quoted(reasoning.observed)}.`
      : "No retrieved source identifiers were recorded.";
  }
  if (
    evaluation.evaluator_name === "builtin.expected_tool" ||
    evaluation.evaluator_name === "builtin.forbidden_tool"
  ) {
    return reasoning.observed.length
      ? `The run called ${quoted(reasoning.observed)}.`
      : "No tool calls were recorded.";
  }
  if (reasoning.observed.length) return `AgentGuard observed ${quoted(reasoning.observed)}.`;
  return reasoning.summary;
}

export function evaluationDecision(evaluation: EvaluationResult): string {
  const reasoning = explainEvaluation(evaluation);
  if (evaluation.passed) {
    return `${reasoning.summary} AgentGuard therefore marked this check as passed.`;
  }
  return `${reasoning.summary} The stored score was below the configured passing threshold, so AgentGuard marked this check as failed.`;
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

export type ApplicationStage = "input" | "retrieval" | "tool" | "workflow" | "generation" | "output";

export interface ObservedApplicationStage {
  id: ApplicationStage;
  label: string;
  detail: string;
  status: "OK" | "ERROR" | "UNKNOWN";
}

export type ArchitectureLayer = "request" | "orchestration" | "context" | "generation" | "response";

export interface ObservedArchitectureNode {
  id: string;
  layer: ArchitectureLayer;
  label: string;
  stereotype: string;
  detail: string;
  status: "OK" | "ERROR" | "UNKNOWN";
  observedRuns: number;
}

export interface ObservedApplicationArchitecture {
  nodes: ObservedArchitectureNode[];
  edges: Array<{ source: string; target: string }>;
  observedRunCount: number;
}

const stageLabels: Record<ApplicationStage, string> = {
  input: "Question",
  retrieval: "Retrieve evidence",
  tool: "Use tools",
  workflow: "Coordinate steps",
  generation: "Generate answer",
  output: "Return answer"
};

function stageForSpan(span: Span): ApplicationStage | null {
  if (span.type === "RETRIEVER" || span.type === "EMBEDDING" || span.type === "RERANKER") return "retrieval";
  if (span.type === "TOOL") return "tool";
  if (span.type === "LLM") return "generation";
  if (span.type === "AGENT" || span.type === "CHAIN" || span.type === "CUSTOM") return "workflow";
  return null;
}

function architectureLayerForSpan(span: Span): ArchitectureLayer {
  if (span.type === "LLM") return "generation";
  if (["RETRIEVER", "EMBEDDING", "RERANKER", "TOOL"].includes(span.type)) return "context";
  return "orchestration";
}

function architectureDetail(span: Span): string {
  if (span.type === "LLM") {
    return [span.provider, span.model_name].filter(Boolean).join(" / ") || "Recorded model call";
  }
  if (span.type === "RETRIEVER") return "Retrieval component";
  if (span.type === "EMBEDDING") return "Embedding component";
  if (span.type === "RERANKER") return "Reranking component";
  if (span.type === "TOOL") return "Application tool or action";
  if (span.type === "AGENT") return "Agent orchestration";
  if (span.type === "CHAIN") return "Application workflow";
  return "Instrumented application component";
}

function architectureNodeId(span: Span): string {
  return `${span.type}:${span.name}:${span.provider ?? ""}:${span.model_name ?? ""}`;
}

export function observedApplicationArchitecture(traces: Trace[]): ObservedApplicationArchitecture {
  const usable = traces.filter((trace) => trace.spans.length > 0);
  if (!usable.length) return { nodes: [], edges: [], observedRunCount: 0 };

  const runIdsByNode = new Map<string, Set<string>>();
  const nodes = new Map<string, ObservedArchitectureNode>();
  const edges = new Map<string, { source: string; target: string }>();
  for (const trace of usable) {
    const canonicalIdBySpanId = new Map(trace.spans.map((span) => [span.id, architectureNodeId(span)]));
    const parentIds = new Set(trace.spans.map((span) => span.parent_span_id).filter(Boolean));
    for (const span of trace.spans) {
      const id = architectureNodeId(span);
      const runIds = runIdsByNode.get(id) ?? new Set<string>();
      runIds.add(trace.id);
      runIdsByNode.set(id, runIds);
      const current = nodes.get(id);
      nodes.set(id, {
        id,
        layer: architectureLayerForSpan(span),
        label: span.name,
        stereotype: span.type.toLowerCase(),
        detail: architectureDetail(span),
        status: current?.status === "ERROR" || span.status === "ERROR" ? "ERROR" : "OK",
        observedRuns: runIds.size
      });
      const source = span.parent_span_id
        ? canonicalIdBySpanId.get(span.parent_span_id) ?? "request"
        : "request";
      edges.set(`${source}->${id}`, { source, target: id });
      if (!parentIds.has(span.id)) {
        edges.set(`${id}->response`, { source: id, target: "response" });
      }
    }
  }

  return {
    observedRunCount: usable.length,
    edges: [...edges.values()],
    nodes: [
      {
        id: "request",
        layer: "request",
        label: "Application request",
        stereotype: "input",
        detail: "Input received by the instrumented application",
        status: "OK",
        observedRuns: usable.length
      },
      ...nodes.values(),
      {
        id: "response",
        layer: "response",
        label: "Application response",
        stereotype: "output",
        detail: "Output returned by the instrumented application",
        status: usable.some((trace) => trace.status === "ERROR") ? "ERROR" : "OK",
        observedRuns: usable.length
      }
    ]
  };
}

export function architectureLayerForDifference(stage: ApplicationStage | null): ArchitectureLayer | null {
  if (stage === "input") return "request";
  if (stage === "retrieval" || stage === "tool") return "context";
  if (stage === "generation") return "generation";
  if (stage === "workflow") return "orchestration";
  if (stage === "output") return "response";
  return null;
}

export function observedApplicationFlow(trace: Trace | null): ObservedApplicationStage[] {
  if (!trace) return [];
  const stages = new Map<ApplicationStage, ObservedApplicationStage>();
  stages.set("input", {
    id: "input",
    label: stageLabels.input,
    detail: "The application received the test-case input.",
    status: trace.input ? "OK" : "UNKNOWN"
  });

  const sorted = [...trace.spans].sort(
    (left, right) => Date.parse(left.started_at) - Date.parse(right.started_at)
  );
  for (const span of sorted) {
    const stage = stageForSpan(span);
    if (!stage) continue;
    const current = stages.get(stage);
    const failed = span.status === "ERROR" || current?.status === "ERROR";
    const names = current?.detail
      ? new Set(current.detail.split(", ").map((value) => value.trim()))
      : new Set<string>();
    names.add(span.name);
    stages.set(stage, {
      id: stage,
      label: stageLabels[stage],
      detail: [...names].join(", "),
      status: failed ? "ERROR" : "OK"
    });
  }

  stages.set("output", {
    id: "output",
    label: stageLabels.output,
    detail: traceAnswer(trace)
      ? "The run returned a recorded answer."
      : "No answer was recorded for this run.",
    status: trace.status === "ERROR" ? "ERROR" : trace.output ? "OK" : "UNKNOWN"
  });
  return [...stages.values()];
}

export function firstSupportedDifference(evaluations: EvaluationResult[]): ApplicationStage | null {
  const failed = evaluations.filter((evaluation) => !evaluation.passed);
  if (!failed.length) return null;
  const categories = failed.map((evaluation) => evaluatorInfo(evaluation.evaluator_name).category);
  if (categories.includes("Retrieval")) return "retrieval";
  if (categories.includes("Agent Behavior")) return "tool";
  if (categories.includes("Answer Quality")) return "generation";
  if (categories.includes("Operational")) return "workflow";
  return null;
}
