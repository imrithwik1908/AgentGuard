import Link from "next/link";

import { ApiUnavailable } from "@/components/api-unavailable";
import { EvaluationStatusBadge } from "@/components/evaluation-status-badge";
import {
  comparePairedVersions,
  getReleaseDecision,
  listEvaluations,
  listProjects,
  listTraces,
  listVersions
} from "@/lib/api";
import { formatPercent, formatScore } from "@/lib/format";
import {
  findComparisonPair,
  findDefaultComparisonPair,
  type ChangeItem,
  type RegressionCase,
  type RegressionBuckets,
  summarizeConfigChanges
} from "@/lib/product-intelligence";
import { evaluatorInfo, numeric } from "@/lib/product-intelligence";
import type {
  ApplicationVersion,
  CaseComparison,
  EvaluationResult,
  PairedVersionComparison,
  Project,
  ReleaseDecision,
  Trace
} from "@/lib/types";

function versionLabel(version: ApplicationVersion, projects: Project[]) {
  const project = projects.find((candidate) => candidate.id === version.project_id);
  return `${project?.name ?? "Project"} / ${version.version}`;
}

function decisionClasses(tone: "ok" | "error" | "warning" | "neutral") {
  if (tone === "ok") return "border-emerald-200 bg-emerald-50 text-emerald-950";
  if (tone === "error") return "border-red-200 bg-red-50 text-red-950";
  if (tone === "warning") return "border-amber-200 bg-amber-50 text-amber-950";
  return "border-slate-200 bg-slate-50 text-slate-950";
}

export default async function ReleasesPage({
  searchParams
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const query = await searchParams;
  let baselineVersionId = typeof query.baseline_version_id === "string" ? query.baseline_version_id : "";
  let candidateVersionId = typeof query.candidate_version_id === "string" ? query.candidate_version_id : "";

  let projects;
  let versions;
  let evaluations;
  let traces;
  try {
    projects = await listProjects();
    versions = (await Promise.all(projects.map((project) => listVersions(project.id)))).flat();
    evaluations = await listEvaluations({ limit: 200 });
    traces = await listTraces({ limit: 200 });
  } catch (error) {
    return (
      <ApiUnavailable
        title="Release workflow cannot reach the AgentGuard API"
        detail={error instanceof Error ? error.message : String(error)}
      />
    );
  }

  const fallbackPair = findDefaultComparisonPair(projects, versions);
  if (!baselineVersionId && fallbackPair) baselineVersionId = fallbackPair.baseline.id;
  if (!candidateVersionId && fallbackPair) candidateVersionId = fallbackPair.candidate.id;

  const pair = baselineVersionId && candidateVersionId
    ? findComparisonPair(projects, versions, baselineVersionId, candidateVersionId)
    : null;
  let comparison: PairedVersionComparison | null = null;
  let policyDecision: ReleaseDecision | null = null;
  try {
    if (pair) {
      [comparison, policyDecision] = await Promise.all([
        comparePairedVersions(pair.baseline.id, pair.candidate.id),
        getReleaseDecision(pair.baseline.id, pair.candidate.id)
      ]);
    }
  } catch (error) {
    return (
      <ApiUnavailable
        title="Release comparison failed"
        detail={error instanceof Error ? error.message : String(error)}
      />
    );
  }

  const buckets = comparison
    ? bucketsFromPairedComparison(comparison, evaluations.items, traces.items)
    : { regressed: [], improved: [], unchanged: [], notComparable: [] };
  const releaseState = releaseStateFromDecision(policyDecision);
  const changes = pair ? summarizeConfigChanges(pair.baseline, pair.candidate) : [];
  const comparedCount =
    comparison?.comparable_case_count ??
    buckets.regressed.length + buckets.improved.length + buckets.unchanged.length;

  return (
    <div className="space-y-8">
      <section className={`rounded-[2rem] border p-6 shadow-panel ${decisionClasses(releaseState.tone)}`}>
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="text-xs font-medium uppercase tracking-[0.22em] opacity-70">
              Release decision
            </div>
            <h1 className="mt-3 text-4xl font-semibold tracking-normal">{releaseState.title}</h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 opacity-80">
              {pair
                ? `${pair.project.name}: candidate ${pair.candidate.version} compared with baseline ${pair.baseline.version}.`
                : "Choose two versions from the same project to compare behavior."}
            </p>
            <p className="mt-2 max-w-3xl text-sm leading-6 opacity-80">{releaseState.explanation}</p>
            {policyDecision?.reasons.length ? (
              <ul className="mt-3 space-y-1 text-sm opacity-80">
                {policyDecision.reasons.slice(0, 3).map((reason) => (
                  <li key={reason}>• {reason}</li>
                ))}
              </ul>
            ) : null}
          </div>
          {pair ? (
            <div className="rounded-2xl bg-white/70 p-4 shadow-sm">
              <div className="text-xs uppercase tracking-wide opacity-60">Compared evidence</div>
              <div className="mt-2 text-3xl font-semibold">{comparedCount}</div>
              <p className="mt-2 max-w-sm text-sm leading-5 opacity-75">
                {formatPercent(comparison?.comparison_coverage)} comparison coverage: paired case checks with evidence from both versions.
              </p>
            </div>
          ) : null}
        </div>

        <div className="mt-6 grid gap-3 md:grid-cols-4">
          <Metric label="Regressed" value={buckets.regressed.length} detail="Paired checks worse in candidate" />
          <Metric label="Improved" value={buckets.improved.length} detail="Paired checks fixed or improved" />
          <Metric label="Unchanged" value={buckets.unchanged.length} detail="Equivalent paired checks" />
          <Metric label="Not comparable" value={buckets.notComparable.length} detail="Missing evidence from one side" />
        </div>
      </section>

      <section className="overflow-hidden rounded-[2rem] border border-slate-200 bg-white shadow-panel">
        <div className="border-b border-slate-200 bg-slate-50/80 p-5">
          <h2 className="text-lg font-semibold text-ink-950">Compare versions</h2>
          <p className="mt-1 text-sm text-slate-600">
            AgentGuard pairs the same test-case checks across versions. AI-assisted explanations
            appear only when a judge is configured and its evidence is stored.
          </p>
        </div>
        <form className="grid gap-3 p-5 md:grid-cols-[1fr_1fr_auto]">
          <label className="grid gap-1 text-xs font-medium uppercase tracking-wide text-slate-500">
            Baseline
            <select
              name="baseline_version_id"
              defaultValue={baselineVersionId}
              className="rounded border border-slate-300 px-3 py-2 text-sm font-normal normal-case tracking-normal text-ink-950"
            >
              <option value="">Choose baseline</option>
              {versions.map((version) => (
                <option key={version.id} value={version.id}>
                  {versionLabel(version, projects)}
                </option>
              ))}
            </select>
          </label>
          <label className="grid gap-1 text-xs font-medium uppercase tracking-wide text-slate-500">
            Candidate
            <select
              name="candidate_version_id"
              defaultValue={candidateVersionId}
              className="rounded border border-slate-300 px-3 py-2 text-sm font-normal normal-case tracking-normal text-ink-950"
            >
              <option value="">Choose candidate</option>
              {versions.map((version) => (
                <option key={version.id} value={version.id}>
                  {versionLabel(version, projects)}
                </option>
              ))}
            </select>
          </label>
          <button className="self-end rounded-full bg-ink-900 px-5 py-2 text-sm font-medium text-white">
            Compare
          </button>
        </form>
      </section>

      {comparison && pair ? (
        <section className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
          <div className="surface rounded-[2rem] p-5">
            <div className="text-xs font-medium uppercase tracking-[0.2em] text-cyan-700">
              Score movement
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <Metric label="Answer-check score" value={scoreMovementLabel(comparison.score_delta)} detail="Average stored check score moved candidate vs baseline" />
              <Metric label="Pass-rate movement" value={formatPercent(comparison.pass_rate_delta)} detail="Share of stored checks that passed" />
              <Metric label="Baseline checks" value={comparison.baseline.evaluation_count} detail={`${comparison.baseline.pass_count} passing`} />
              <Metric label="Candidate checks" value={comparison.candidate.evaluation_count} detail={`${comparison.candidate.fail_count} failing`} />
            </div>
          </div>

          <div className="surface rounded-[2rem] p-5">
            <div className="text-xs font-medium uppercase tracking-[0.2em] text-cyan-700">
              Observed configuration change
            </div>
            <div className="mt-4">
              <ConfigChangeList
                baselineLabel={pair.baseline.version}
                candidateLabel={pair.candidate.version}
                changes={changes}
              />
            </div>
            <p className="mt-4 text-xs leading-5 text-slate-500">
              These are observed stored configuration differences only. Behavioral causality is not
              inferred unless a specific evaluator provides evidence.
            </p>
          </div>
        </section>
      ) : null}

      {comparison?.failure_clusters?.length ? (
        <section className="surface rounded-[2rem] p-5">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <div className="text-xs font-medium uppercase tracking-[0.2em] text-cyan-700">
                Failure groups
              </div>
              <h2 className="mt-2 text-lg font-semibold text-ink-950">
                AgentGuard grouped the regressions by observed evidence
              </h2>
              <p className="mt-1 text-sm text-slate-600">
                These groups summarize patterns. They do not claim the configuration change caused the failure.
              </p>
            </div>
            <div className="text-sm font-medium text-slate-600">
              {comparison.failure_clusters.reduce((total, cluster) => total + cluster.case_count, 0)} regressed checks grouped
            </div>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {comparison.failure_clusters.map((cluster) => (
              <div key={`${cluster.likely_failure_stage}:${cluster.evaluator_names.join(",")}`} className="rounded-2xl border border-slate-200 bg-white p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="font-semibold text-ink-950">{cluster.label}</h3>
                    <p className="mt-1 text-sm leading-5 text-slate-600">{cluster.summary}</p>
                  </div>
                  <div className="rounded-full bg-red-50 px-2.5 py-1 text-xs font-semibold text-red-700">
                    {cluster.case_count}
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap gap-1">
                  {cluster.evaluator_names.map((name) => (
                    <span key={name} className="rounded-full bg-slate-100 px-2 py-1 text-[11px] text-slate-600">
                      {evaluatorInfo(name).name}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section className="space-y-4">
        <SectionHeader
          title="Regressions to investigate"
          description="Cases that worked better in the baseline than in this candidate."
        />
        <CaseList items={buckets.regressed} empty="No paired regressions found for this comparison." tone="regressed" />
      </section>

      <section className="grid gap-5 lg:grid-cols-2">
        <div className="space-y-4">
          <SectionHeader title="Improvements" description="Checks the candidate fixed or improved." />
          <CaseList items={buckets.improved} empty="No paired improvements found yet." tone="improved" />
        </div>
        <div className="space-y-4">
          <SectionHeader title="Unchanged" description="Checks that remained equivalent." />
          <CaseList items={buckets.unchanged.slice(0, 6)} empty="No unchanged paired checks yet." tone="unchanged" />
        </div>
      </section>

      <section className="space-y-4">
        <SectionHeader
          title="Not comparable yet"
          description="Cases missing baseline or candidate evidence. These are not regressions."
        />
        <CaseList items={buckets.notComparable.slice(0, 8)} empty="Every visible case has evidence from both versions." tone="unchanged" />
      </section>
    </div>
  );
}

function releaseStateFromDecision(decision: ReleaseDecision | null) {
  if (!decision) {
    return {
      title: "Not evaluated",
      explanation: "Choose a baseline and candidate with paired test evidence.",
      tone: "neutral" as const
    };
  }
  if (decision.decision === "PASS") {
    return {
      title: "Safe to ship under this policy",
      explanation: decision.summary,
      tone: "ok" as const
    };
  }
  if (decision.decision === "BLOCK") {
    return {
      title: decision.runtime_failure_count > 0
        ? "Block: runtime failures detected"
        : "Block: regressions detected",
      explanation: decision.summary,
      tone: "error" as const
    };
  }
  return {
    title: "Not enough evidence to decide",
    explanation: decision.summary,
    tone: "warning" as const
  };
}

function bucketsFromPairedComparison(
  comparison: PairedVersionComparison,
  evaluations: EvaluationResult[],
  traces: Trace[]
): RegressionBuckets {
  const evaluationById = new Map(evaluations.map((evaluation) => [evaluation.id, evaluation]));
  const traceById = new Map(traces.map((trace) => [trace.id, trace]));
  return {
    regressed: comparison.regressed.map((item) => regressionCaseFromComparison(item, evaluationById, traceById)),
    improved: comparison.improved.map((item) => regressionCaseFromComparison(item, evaluationById, traceById)),
    unchanged: comparison.unchanged.map((item) => regressionCaseFromComparison(item, evaluationById, traceById)),
    notComparable: comparison.not_comparable.map((item) => regressionCaseFromComparison(item, evaluationById, traceById))
  };
}

function regressionCaseFromComparison(
  item: CaseComparison,
  evaluationById: Map<string, EvaluationResult>,
  traceById: Map<string, Trace>
): RegressionCase {
  const baselineEvaluation = item.baseline_evaluation_id
    ? evaluationById.get(item.baseline_evaluation_id) ?? null
    : null;
  const candidateEvaluation = item.candidate_evaluation_id
    ? evaluationById.get(item.candidate_evaluation_id) ?? null
    : null;
  const baselineEvaluations = baselineEvaluation ? [baselineEvaluation] : [];
  const candidateEvaluations = candidateEvaluation ? [candidateEvaluation] : [];
  const all = [...baselineEvaluations, ...candidateEvaluations];
  const candidateTrace = candidateEvaluation ? traceById.get(candidateEvaluation.trace_id) ?? null : null;
  const baselineTrace = baselineEvaluation ? traceById.get(baselineEvaluation.trace_id) ?? null : null;
  const categories = Array.from(
    new Set(all.map((evaluation) => evaluatorInfo(evaluation.evaluator_name).category))
  );
  const title =
    titleFromTrace(candidateTrace ?? baselineTrace) ??
    candidateEvaluation?.label ??
    baselineEvaluation?.label ??
    "Behavioral test case";
  return {
    key: `${item.dataset_case_id ?? "unknown"}:${item.evaluator_name}`,
    title,
    summary: item.explanation,
    baselineEvaluations,
    candidateEvaluations,
    primaryEvaluation: candidateEvaluation ?? baselineEvaluation,
    failedEvaluations: candidateEvaluations.filter((evaluation) => !evaluation.passed),
    categories,
    baselinePassed: item.baseline_status === "PASS",
    candidatePassed: item.candidate_status === "PASS",
    baselineScore: numeric(item.baseline_score),
    candidateScore: numeric(item.candidate_score),
    scoreDelta: (numeric(item.candidate_score) ?? 0) - (numeric(item.baseline_score) ?? 0),
    baselineTrace,
    candidateTrace,
    failureAnalysis: item.failure_analysis
  };
}

function titleFromTrace(trace: Trace | null): string | null {
  const input = trace?.input;
  if (input && typeof input === "object" && !Array.isArray(input)) {
    const question = input.question;
    if (typeof question === "string") return question;
  }
  return trace?.name ?? null;
}

function Metric({ label, value, detail }: { label: string; value: React.ReactNode; detail: string }) {
  return (
    <div className="rounded-2xl bg-white/70 p-4 shadow-sm">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-ink-950">{value}</div>
      <div className="mt-1 text-xs text-slate-600">{detail}</div>
    </div>
  );
}

function ConfigChangeList({
  baselineLabel,
  candidateLabel,
  changes
}: {
  baselineLabel: string;
  candidateLabel: string;
  changes: ChangeItem[];
}) {
  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
      <div className="grid grid-cols-[1fr_auto_1fr] gap-3 border-b border-slate-100 bg-slate-50 px-4 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">
        <span>{baselineLabel}</span>
        <span>→</span>
        <span className="text-right">{candidateLabel}</span>
      </div>
      <div className="divide-y divide-slate-100">
        {changes.map((change) => (
          <div key={change.label} className="grid gap-3 px-4 py-4 sm:grid-cols-[8rem_1fr_auto_1fr] sm:items-start">
            <div className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-700">
              {configGroupLabel(change.label)}
              {change.field ? (
                <div className="mt-1 break-words font-mono text-[11px] normal-case tracking-normal text-slate-700">
                  {change.field}
                </div>
              ) : null}
            </div>
            <CodeLikeValue value={change.before} />
            <div className="hidden pt-1 text-slate-400 sm:block">→</div>
            <CodeLikeValue value={change.after} align="right" />
          </div>
        ))}
      </div>
      <details className="border-t border-slate-100 px-4 py-3 text-xs text-slate-500">
        <summary className="cursor-pointer font-medium text-slate-600">Raw configuration</summary>
        <div className="mt-3 space-y-2">
          {changes.map((change) => (
            <div key={`${change.label}-raw`} className="rounded-xl bg-slate-950 p-3 font-mono text-[11px] text-slate-100">
              <div>{change.label}{change.field ? ` / ${change.field}` : ""}</div>
              <div className="mt-1 text-slate-300">baseline: {change.before}</div>
              <div className="text-slate-300">candidate: {change.after}</div>
            </div>
          ))}
        </div>
      </details>
    </div>
  );
}

function CodeLikeValue({ value, align = "left" }: { value: string; align?: "left" | "right" }) {
  const isPrompt = value.includes("\\n") || value.length > 80;
  return (
    <div className={align === "right" ? "text-left sm:text-right" : "text-left"}>
      <div className="break-words font-mono text-sm text-ink-950">
        {isPrompt ? "Modified" : value}
      </div>
    </div>
  );
}

function configGroupLabel(label: string): string {
  if (label.toLowerCase().includes("model")) return "MODEL";
  if (label.toLowerCase().includes("retrieval")) return "RETRIEVAL";
  if (label.toLowerCase().includes("prompt")) return "PROMPT";
  if (label.toLowerCase().includes("workflow") || label.toLowerCase().includes("agent")) {
    return "AGENT";
  }
  return "CONFIG";
}

function SectionHeader({ title, description }: { title: string; description: string }) {
  return (
    <div>
      <h2 className="text-lg font-semibold text-ink-950">{title}</h2>
      <p className="mt-1 text-sm text-slate-600">{description}</p>
    </div>
  );
}

function CaseList({
  items,
  empty,
  tone
}: {
  items: RegressionCase[];
  empty: string;
  tone: "regressed" | "improved" | "unchanged";
}) {
  if (items.length === 0) {
    return <div className="surface rounded-2xl p-5 text-sm text-slate-600">{empty}</div>;
  }
  return (
    <div className="space-y-3">
      {items.map((item) => (
        <div key={item.key} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-panel">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
                Behavioral test case · {item.categories.join(", ") || "Evaluation evidence"}
              </div>
              <h3 className="mt-1 text-base font-semibold text-ink-950">{item.title}</h3>
              <p className="mt-1 max-w-3xl text-sm text-slate-600">{item.summary}</p>
              {item.failureAnalysis ? (
                <div className="mt-3 rounded-2xl border border-cyan-100 bg-cyan-50/70 p-3 text-sm text-cyan-950">
                  <div className="text-xs font-semibold uppercase tracking-wide text-cyan-700">
                    AgentGuard analysis
                  </div>
                  <div className="mt-1">{String(item.failureAnalysis.summary ?? "Evidence differs between versions.")}</div>
                  <div className="mt-1 text-xs text-cyan-800">
                    Likely stage: {String(item.failureAnalysis.likely_failure_stage ?? "unknown")} ·
                    Confidence: {String(item.failureAnalysis.confidence ?? "unknown")}
                  </div>
                </div>
              ) : null}
              <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
                <OutcomeBadge passed={item.baselinePassed} empty={item.baselineEvaluations.length === 0} />
                <span className="text-slate-500">baseline</span>
                <span className="text-slate-300">→</span>
                <OutcomeBadge passed={item.candidatePassed} empty={item.candidateEvaluations.length === 0} />
                <span className="text-slate-500">candidate</span>
              </div>
            </div>
            <div className="text-right">
              <div className={tone === "regressed" ? "text-red-700" : tone === "improved" ? "text-emerald-700" : "text-slate-700"}>
                {scoreMovementLabel(item.scoreDelta)}
              </div>
              <div className="text-xs text-slate-500">average score movement</div>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            {item.candidateTrace ? (
              <Link
                href={`/traces/${item.candidateTrace.id}`}
                className="rounded-full bg-ink-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-ink-800"
              >
                Investigate run
              </Link>
            ) : null}
            <details className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600 md:w-auto md:min-w-[34rem]">
              <summary className="cursor-pointer font-medium text-slate-700">Evaluation details</summary>
              <div className="mt-3 grid min-w-0 gap-3 pb-2 text-xs leading-5 lg:grid-cols-2">
                <EvidenceColumn title="Baseline evidence" items={item.baselineEvaluations} />
                <EvidenceColumn title="Candidate evidence" items={item.candidateEvaluations} />
              </div>
            </details>
          </div>
        </div>
      ))}
    </div>
  );
}

function OutcomeBadge({ passed, empty }: { passed: boolean; empty: boolean }) {
  if (empty) {
    return <span className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600">Missing</span>;
  }
  return <EvaluationStatusBadge status={passed ? "PASS" : "FAIL"} />;
}

function EvidenceColumn({ title, items }: { title: string; items: EvaluationResult[] }) {
  if (items.length === 0) {
    return (
      <div>
        <div className="font-medium text-slate-700">{title}</div>
        <div className="mt-1 text-slate-500">No stored check result for this side.</div>
      </div>
    );
  }
  return (
    <div>
      <div className="font-medium text-slate-700">{title}</div>
      <div className="mt-2 space-y-2">
        {items.map((item) => {
          const info = evaluatorInfo(item.evaluator_name);
          return (
            <div key={item.id} className="rounded-xl bg-white p-2">
              <div className="flex items-center justify-between gap-2">
                <span>{info.name}</span>
                <EvaluationStatusBadge status={item.status} />
              </div>
              <div className="mt-1 text-slate-500">
                Score {formatScore(item.score)}
                {item.threshold ? ` · threshold ${formatScore(item.threshold)}` : ""}
              </div>
              <details className="mt-1">
                <summary className="cursor-pointer text-slate-500">Advanced details</summary>
                <div className="mt-1 font-mono text-[11px]">{item.evaluator_name}</div>
              </details>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function scoreMovementLabel(value: string | number | null | undefined): string {
  const parsed = numeric(value);
  if (parsed === null) return "Not available";
  const sign = parsed > 0 ? "+" : "";
  return `${sign}${parsed.toFixed(2)}`;
}
