import type {
  ApplicationVersion,
  EvaluationResult,
  Project,
  Trace,
  VersionComparison
} from "./types";

export type EvaluatorCategory =
  | "Answer Quality"
  | "Retrieval"
  | "Agent Behavior"
  | "Operational";

export interface EvaluatorInfo {
  category: EvaluatorCategory;
  name: string;
  implemented: boolean;
  description: string;
}

export interface ComparablePair {
  project: Project;
  baseline: ApplicationVersion;
  candidate: ApplicationVersion;
}

export interface ChangeItem {
  label: string;
  field?: string;
  before: string;
  after: string;
  evidence: "observed" | "not_configured";
}

export interface RegressionCase {
  key: string;
  title: string;
  summary: string;
  baselineEvaluations: EvaluationResult[];
  candidateEvaluations: EvaluationResult[];
  primaryEvaluation: EvaluationResult | null;
  failedEvaluations: EvaluationResult[];
  categories: EvaluatorCategory[];
  baselinePassed: boolean;
  candidatePassed: boolean;
  baselineScore: number | null;
  candidateScore: number | null;
  scoreDelta: number;
  baselineTrace: Trace | null;
  candidateTrace: Trace | null;
  failureAnalysis?: Record<string, unknown> | null;
}

export interface RegressionBuckets {
  regressed: RegressionCase[];
  improved: RegressionCase[];
  unchanged: RegressionCase[];
  notComparable: RegressionCase[];
}

export type ReleaseState =
  | "PASS"
  | "BLOCK_REGRESSION"
  | "BLOCK_RUNTIME_FAILURE"
  | "INSUFFICIENT_EVIDENCE"
  | "NOT_EVALUATED";

export interface ReleaseStateInfo {
  state: ReleaseState;
  title: string;
  explanation: string;
  tone: "ok" | "error" | "warning" | "neutral";
}

const EVALUATOR_CATALOG: Record<string, EvaluatorInfo> = {
  "builtin.answer_contains": {
    category: "Answer Quality",
    name: "Required content",
    implemented: true,
    description: "Checks whether the generated answer satisfies a required content constraint."
  },
  "builtin.answer_exact": {
    category: "Answer Quality",
    name: "Exact answer match",
    implemented: true,
    description: "Checks whether the answer exactly matches the expected answer."
  },
  "builtin.keyword_coverage": {
    category: "Answer Quality",
    name: "Keyword coverage",
    implemented: true,
    description: "Scores how many required keywords appear in the generated answer."
  },
  "builtin.required_content": {
    category: "Answer Quality",
    name: "Required content",
    implemented: true,
    description: "Checks whether the generated answer satisfies a required content constraint."
  },
  "builtin.exact_answer": {
    category: "Answer Quality",
    name: "Exact answer match",
    implemented: true,
    description: "Checks normalized exact equality with the expected answer."
  },
  "builtin.structured_output": {
    category: "Answer Quality",
    name: "Structured output",
    implemented: true,
    description: "Checks JSON output against the schema configured by the test case."
  },
  "builtin.semantic_correctness": {
    category: "Answer Quality",
    name: "Semantic correctness",
    implemented: true,
    description: "Uses a rubric-based LLM judge to compare the answer with the expected meaning."
  },
  "builtin.groundedness": {
    category: "Answer Quality",
    name: "Groundedness",
    implemented: true,
    description: "Uses a rubric-based LLM judge to check whether material claims are supported by retrieved evidence."
  },
  "builtin.required_source": {
    category: "Retrieval",
    name: "Required source",
    implemented: true,
    description: "Checks whether every source required by the test case was retrieved."
  },
  "builtin.retrieval_relevance": {
    category: "Retrieval",
    name: "Retrieval relevance",
    implemented: true,
    description: "Judges whether retrieved evidence is relevant to the request."
  },
  "builtin.expected_tool": {
    category: "Agent Behavior",
    name: "Expected tool",
    implemented: true,
    description: "Checks whether the application called the tool required by the test case."
  },
  "builtin.forbidden_tool": {
    category: "Agent Behavior",
    name: "Forbidden tool avoided",
    implemented: true,
    description: "Checks that prohibited tools were not called."
  },
  "builtin.tool_selection": {
    category: "Agent Behavior",
    name: "Tool selection",
    implemented: true,
    description: "Judges whether the selected tool was appropriate for the request and available tools."
  },
  "builtin.runtime_success": {
    category: "Operational",
    name: "Runtime success",
    implemented: true,
    description: "Checks whether the application execution completed successfully."
  },
  "builtin.latency": {
    category: "Operational",
    name: "Latency budget",
    implemented: true,
    description: "Checks total run duration against the test case latency budget."
  },
  "builtin.trace_status": {
    category: "Operational",
    name: "Runtime success",
    implemented: true,
    description: "Checks whether the run completed without an ERROR trace status."
  },
  "builtin.trace_health.status": {
    category: "Operational",
    name: "Run completed",
    implemented: true,
    description: "Checks whether the top-level run completed."
  },
  "builtin.trace_health.error_spans": {
    category: "Operational",
    name: "Nested step errors",
    implemented: true,
    description: "Checks whether any internal step captured an exception or ERROR status."
  },
  "builtin.trace_health.latency_budget": {
    category: "Operational",
    name: "Latency budget",
    implemented: true,
    description: "Scores run duration against the configured latency budget."
  },
  "builtin.trace_health.evidence": {
    category: "Operational",
    name: "Debug evidence",
    implemented: true,
    description: "Checks whether spans contain inputs, outputs, or errors for investigation."
  }
};

export const PLANNED_EVALUATORS: EvaluatorInfo[] = [
  {
    category: "Answer Quality",
    name: "Hallucination pattern analysis",
    implemented: false,
    description: "Future analysis for recurring unsupported-claim patterns across evaluation runs."
  },
  {
    category: "Retrieval",
    name: "Semantic retrieval coverage",
    implemented: false,
    description: "Future embedding-assisted analysis for evidence coverage beyond explicit source IDs."
  },
  {
    category: "Agent Behavior",
    name: "Trajectory policy compliance",
    implemented: false,
    description: "Future evaluator for multi-step workflow and policy constraints."
  }
];

export function evaluatorInfo(evaluatorName: string): EvaluatorInfo {
  return (
    EVALUATOR_CATALOG[evaluatorName] ?? {
      category: evaluatorName.includes("retriev") || evaluatorName.includes("source")
        ? "Retrieval"
        : evaluatorName.includes("tool")
          ? "Agent Behavior"
          : "Operational",
      name: humanizeEvaluatorName(evaluatorName),
      implemented: true,
      description: "Stored evaluator result from the AgentGuard API."
    }
  );
}

export function implementedEvaluatorCatalog(): EvaluatorInfo[] {
  return Array.from(
    new Map(
      Object.values(EVALUATOR_CATALOG).map((item) => [`${item.category}:${item.name}`, item])
    ).values()
  );
}

export function isJudgeEvaluator(evaluatorName: string): boolean {
  return [
    "builtin.semantic_correctness",
    "builtin.groundedness",
    "builtin.retrieval_relevance",
    "builtin.tool_selection",
    "Semantic correctness",
    "Groundedness",
    "Retrieval relevance",
    "Tool selection"
  ].includes(evaluatorName);
}

export function findDefaultComparisonPair(
  projects: Project[],
  versions: ApplicationVersion[]
): ComparablePair | null {
  for (const project of projects) {
    const projectVersions = versions
      .filter((version) => version.project_id === project.id)
      .sort((left, right) => Date.parse(left.created_at) - Date.parse(right.created_at));
    if (projectVersions.length >= 2) {
      return {
        project,
        baseline: projectVersions[projectVersions.length - 2],
        candidate: projectVersions[projectVersions.length - 1]
      };
    }
  }
  return null;
}

export function findComparisonPair(
  projects: Project[],
  versions: ApplicationVersion[],
  baselineVersionId: string,
  candidateVersionId: string
): ComparablePair | null {
  const baseline = versions.find((version) => version.id === baselineVersionId);
  const candidate = versions.find((version) => version.id === candidateVersionId);
  if (!baseline || !candidate || baseline.project_id !== candidate.project_id) return null;
  const project = projects.find((item) => item.id === baseline.project_id);
  if (!project) return null;
  return { project, baseline, candidate };
}

export function summarizeConfigChanges(
  baseline: ApplicationVersion,
  candidate: ApplicationVersion
): ChangeItem[] {
  const fields: Array<[string, keyof ApplicationVersion]> = [
    ["Model configuration", "model_config"],
    ["Prompt configuration", "prompt_config"],
    ["Retrieval configuration", "retrieval_config"],
    ["Agent workflow configuration", "agent_config"],
    ["Version metadata", "metadata"]
  ];
  const changes: ChangeItem[] = [];
  for (const [label, key] of fields) {
    const beforeConfig = asConfigRecord(baseline[key]);
    const afterConfig = asConfigRecord(candidate[key]);
    const configKeys = [...new Set([...Object.keys(beforeConfig), ...Object.keys(afterConfig)])].sort();
    for (const configKey of configKeys) {
      const before = JSON.stringify(beforeConfig[configKey] ?? null);
      const after = JSON.stringify(afterConfig[configKey] ?? null);
      if (before === after) continue;
      changes.push({
        label,
        field: configKey,
        before: compactJson(formatConfigValue(beforeConfig[configKey])),
        after: compactJson(formatConfigValue(afterConfig[configKey])),
        evidence: "observed"
      });
    }
  }

  return changes.length > 0
    ? changes
    : [
        {
          label: "Configuration diff",
          before: "No stored config difference",
          after: "No stored config difference",
          evidence: "not_configured"
        }
      ];
}

function asConfigRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function formatConfigValue(value: unknown): string {
  if (value === undefined) return "Not set";
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

export function classifyEvaluationPairs({
  evaluations,
  traces,
  baselineVersionId,
  candidateVersionId,
  meaningfulScoreDelta = 0.05
}: {
  evaluations: EvaluationResult[];
  traces: Trace[];
  baselineVersionId: string;
  candidateVersionId: string;
  meaningfulScoreDelta?: number;
}): RegressionBuckets {
  const traceById = new Map(traces.map((trace) => [trace.id, trace]));
  const baseline = new Map<string, EvaluationResult[]>();
  const candidate = new Map<string, EvaluationResult[]>();
  const notComparable: RegressionCase[] = [];

  for (const evaluation of evaluations) {
    const key = pairKey(evaluation);
    if (!key) continue;
    if (evaluation.application_version_id === baselineVersionId) {
      appendEvaluation(baseline, key, evaluation);
    }
    if (evaluation.application_version_id === candidateVersionId) {
      appendEvaluation(candidate, key, evaluation);
    }
  }

  const regressed: RegressionCase[] = [];
  const improved: RegressionCase[] = [];
  const unchanged: RegressionCase[] = [];
  const keys = new Set([...baseline.keys(), ...candidate.keys()]);

  for (const key of keys) {
    const baselineEvaluations = baseline.get(key) ?? [];
    const candidateEvaluations = candidate.get(key) ?? [];
    const item = toRegressionCase(key, baselineEvaluations, candidateEvaluations, traceById);
    if (baselineEvaluations.length === 0 || candidateEvaluations.length === 0) {
      notComparable.push(item);
      continue;
    }
    if (
      (item.baselinePassed && !item.candidatePassed) ||
      item.scoreDelta <= -meaningfulScoreDelta
    ) {
      regressed.push(item);
    } else if (
      (!item.baselinePassed && item.candidatePassed) ||
      item.scoreDelta >= meaningfulScoreDelta
    ) {
      improved.push(item);
    } else {
      unchanged.push(item);
    }
  }

  return { regressed, improved, unchanged, notComparable };
}

export function deriveReleaseState(
  buckets: RegressionBuckets,
  comparison: VersionComparison | null
): ReleaseStateInfo {
  const comparedCount = buckets.regressed.length + buckets.improved.length + buckets.unchanged.length;
  const candidateHasNoResults = comparison?.candidate.evaluation_count === 0;
  if (!comparison || candidateHasNoResults) {
    return {
      state: "NOT_EVALUATED",
      title: "Not evaluated yet",
      explanation: "Run a test suite against the candidate before making a release decision.",
      tone: "neutral"
    };
  }
  if (comparedCount === 0) {
    return {
      state: "INSUFFICIENT_EVIDENCE",
      title: "Not enough evidence to decide",
      explanation:
        "AgentGuard needs the same behavioral test cases evaluated in both baseline and candidate.",
      tone: "warning"
    };
  }
  if (buckets.regressed.some((item) => item.candidateTrace?.status === "ERROR")) {
    return {
      state: "BLOCK_RUNTIME_FAILURE",
      title: "Block: runtime failures",
      explanation: "At least one compared test case failed while the candidate application was running.",
      tone: "error"
    };
  }
  if (buckets.regressed.length > 0) {
    return {
      state: "BLOCK_REGRESSION",
      title: "Block: regressions detected",
      explanation:
        "A regression is a case that worked better in the baseline than in this candidate.",
      tone: "error"
    };
  }
  return {
    state: "PASS",
    title: "Safe to ship",
    explanation: "No paired behavioral regressions were detected in the current comparison.",
    tone: "ok"
  };
}

export function overallLabel(
  comparison: VersionComparison | null,
  state?: ReleaseStateInfo | null
): "IMPROVED" | "REGRESSION" | "REVIEW" | "UNKNOWN" {
  if (!comparison || !state) return "UNKNOWN";
  if (state.state === "BLOCK_REGRESSION" || state.state === "BLOCK_RUNTIME_FAILURE") {
    return "REGRESSION";
  }
  if (state.state === "INSUFFICIENT_EVIDENCE" || state.state === "NOT_EVALUATED") return "UNKNOWN";
  const scoreDelta = numeric(comparison.score_delta);
  const passRateDelta = numeric(comparison.pass_rate_delta);
  if ((scoreDelta ?? 0) > 0 || (passRateDelta ?? 0) > 0) return "IMPROVED";
  return "REVIEW";
}

export function numeric(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined) return null;
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function pairKey(evaluation: EvaluationResult): string | null {
  if (!evaluation.dataset_case_id) return null;
  return evaluation.dataset_case_id;
}

function toRegressionCase(
  key: string,
  baselineEvaluations: EvaluationResult[],
  candidateEvaluations: EvaluationResult[],
  traceById: Map<string, Trace>
): RegressionCase {
  const all = [...candidateEvaluations, ...baselineEvaluations];
  const primary = candidateEvaluations.find((item) => !item.passed) ?? candidateEvaluations[0] ?? null;
  const failedEvaluations = candidateEvaluations.filter((item) => !item.passed);
  const baselineScore = averageScore(baselineEvaluations);
  const candidateScore = averageScore(candidateEvaluations);
  const categories = Array.from(
    new Set(all.map((evaluation) => evaluatorInfo(evaluation.evaluator_name).category))
  );
  const baselineTrace = baselineEvaluations[0]
    ? traceById.get(baselineEvaluations[0].trace_id) ?? null
    : null;
  const candidateTrace = candidateEvaluations[0]
    ? traceById.get(candidateEvaluations[0].trace_id) ?? null
    : null;
  return {
    key,
    title: titleForCase(primary ?? baselineEvaluations[0] ?? null, candidateTrace ?? baselineTrace),
    summary: summaryForCase(primary),
    baselineEvaluations,
    candidateEvaluations,
    primaryEvaluation: primary,
    failedEvaluations,
    categories,
    baselinePassed: baselineEvaluations.length > 0 && baselineEvaluations.every((item) => item.passed),
    candidatePassed: candidateEvaluations.length > 0 && candidateEvaluations.every((item) => item.passed),
    baselineScore,
    candidateScore,
    scoreDelta: (candidateScore ?? 0) - (baselineScore ?? 0),
    baselineTrace,
    candidateTrace
  };
}

function appendEvaluation(
  map: Map<string, EvaluationResult[]>,
  key: string,
  evaluation: EvaluationResult
) {
  map.set(key, [...(map.get(key) ?? []), evaluation]);
}

function averageScore(evaluations: EvaluationResult[]): number | null {
  if (evaluations.length === 0) return null;
  const scores = evaluations.map((evaluation) => numeric(evaluation.score) ?? 0);
  return scores.reduce((total, score) => total + score, 0) / scores.length;
}

function titleForCase(evaluation: EvaluationResult | null, trace: Trace | null): string {
  const question = trace?.input && typeof trace.input === "object" && !Array.isArray(trace.input)
    ? trace.input.question
    : null;
  if (typeof question === "string") return question;
  const expected = evaluation?.metadata?.expected_substring;
  if (typeof expected === "string") return `Expected content: ${expected}`;
  return evaluation?.label ?? trace?.name ?? "Behavioral test case";
}

function summaryForCase(evaluation: EvaluationResult | null): string {
  if (evaluation?.explanation) return evaluation.explanation;
  if (evaluation?.label) return evaluation.label;
  return "Compared using stored deterministic AgentGuard checks.";
}

function humanizeEvaluatorName(value: string): string {
  return value
    .replace(/^builtin\./, "")
    .replaceAll("_", " ")
    .replaceAll(".", " / ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function compactJson(value: string): string {
  if (value.length <= 90) return value;
  return `${value.slice(0, 87)}...`;
}
