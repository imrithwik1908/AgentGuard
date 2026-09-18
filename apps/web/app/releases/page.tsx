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
  explainEvaluation,
  evaluationReliability,
  observedRuntimeChanges,
  retrievalIds,
  toolNames,
  traceAnswer
} from "@/lib/evaluation-explanations";
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
  const representativeCase = [
    ...buckets.regressed,
    ...buckets.improved,
    ...buckets.unchanged
  ].find((item) => item.baselineTrace && item.candidateTrace) ?? null;
  const storedChanges = pair ? summarizeConfigChanges(pair.baseline, pair.candidate) : [];
  const runtimeChanges = representativeCase
    ? observedRuntimeChanges(representativeCase.baselineTrace, representativeCase.candidateTrace).map(
        (change) => ({ ...change, evidence: "observed" as const })
      )
    : [];
  const changes = runtimeChanges.length
    ? mergeChanges(storedChanges.filter((change) => change.evidence === "observed"), runtimeChanges)
    : storedChanges;
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
              <div className="text-xs uppercase tracking-wide opacity-60">Paired evaluator checks</div>
              <div className="mt-2 text-3xl font-semibold">{comparedCount}</div>
              <p className="mt-2 max-w-sm text-sm leading-5 opacity-75">
                {formatPercent(comparison?.comparison_coverage)} evaluator coverage: the share of relevant checks with evidence from both versions.
              </p>
            </div>
          ) : null}
        </div>

        <div className="mt-6 grid gap-3 md:grid-cols-4">
          <Metric label="Regressed behaviors" value={buckets.regressed.length} detail="Test cases with at least one worse check" />
          <Metric label="Improved behaviors" value={buckets.improved.length} detail="Test cases that fixed or improved checks" />
          <Metric label="Unchanged behaviors" value={buckets.unchanged.length} detail="Test cases with equivalent evidence" />
          <Metric label="Not comparable" value={buckets.notComparable.length} detail="Test cases missing evidence from one side" />
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
              Observed application changes
            </div>
            <div className="mt-4">
              <ConfigChangeList
                baselineLabel={pair.baseline.version}
                candidateLabel={pair.candidate.version}
                changes={changes}
              />
            </div>
            <p className="mt-4 text-xs leading-5 text-slate-500">
              These differences come from registered version configuration or recorded run metadata.
              They coincided with the evaluation result; AgentGuard does not claim they caused it.
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
        <CaseList items={buckets.regressed} empty="No paired regressions found for this comparison." tone="regressed" baselineLabel={pair?.baseline.version} candidateLabel={pair?.candidate.version} baselineVersionId={pair?.baseline.id} candidateVersionId={pair?.candidate.id} />
      </section>

      <section className="grid gap-5 lg:grid-cols-2">
        <div className="space-y-4">
          <SectionHeader title="Improvements" description="Checks the candidate fixed or improved." />
          <CaseList items={buckets.improved} empty="No paired improvements found yet." tone="improved" baselineLabel={pair?.baseline.version} candidateLabel={pair?.candidate.version} baselineVersionId={pair?.baseline.id} candidateVersionId={pair?.candidate.id} />
        </div>
        <div className="space-y-4">
          <SectionHeader title="Unchanged" description="Checks that remained equivalent." />
          <CaseList items={buckets.unchanged.slice(0, 6)} empty="No unchanged paired checks yet." tone="unchanged" baselineLabel={pair?.baseline.version} candidateLabel={pair?.candidate.version} baselineVersionId={pair?.baseline.id} candidateVersionId={pair?.candidate.id} compact />
        </div>
      </section>

      <section className="space-y-4">
        <SectionHeader
          title="Not comparable yet"
          description="Cases missing baseline or candidate evidence. These are not regressions."
        />
        <CaseList items={buckets.notComparable.slice(0, 8)} empty="Every visible case has evidence from both versions." tone="unchanged" baselineLabel={pair?.baseline.version} candidateLabel={pair?.candidate.version} baselineVersionId={pair?.baseline.id} candidateVersionId={pair?.candidate.id} compact />
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
  const grouped = new Map<string, Array<{ item: CaseComparison; classification: CaseComparison["classification"] }>>();
  for (const [classification, items] of [
    ["REGRESSED", comparison.regressed],
    ["IMPROVED", comparison.improved],
    ["UNCHANGED", comparison.unchanged],
    ["NOT_COMPARABLE", comparison.not_comparable]
  ] as const) {
    for (const item of items) {
      const key = item.dataset_case_id ?? `unpaired:${item.evaluator_name}`;
      const values = grouped.get(key) ?? [];
      values.push({ item, classification });
      grouped.set(key, values);
    }
  }

  const buckets: RegressionBuckets = { regressed: [], improved: [], unchanged: [], notComparable: [] };
  for (const [key, entries] of grouped) {
    const item = regressionCaseFromComparisons(key, entries.map((entry) => entry.item), evaluationById, traceById);
    const classifications = new Set(entries.map((entry) => entry.classification));
    if (classifications.has("REGRESSED")) buckets.regressed.push(item);
    else if (classifications.has("IMPROVED")) buckets.improved.push(item);
    else if (classifications.has("NOT_COMPARABLE")) buckets.notComparable.push(item);
    else buckets.unchanged.push(item);
  }
  return buckets;
}

function regressionCaseFromComparisons(
  key: string,
  items: CaseComparison[],
  evaluationById: Map<string, EvaluationResult>,
  traceById: Map<string, Trace>
): RegressionCase {
  const baselineEvaluations = uniqueEvaluations(items.flatMap((item) => {
    const evaluation = item.baseline_evaluation_id ? evaluationById.get(item.baseline_evaluation_id) : null;
    return evaluation ? [evaluation] : [];
  }));
  const candidateEvaluations = uniqueEvaluations(items.flatMap((item) => {
    const evaluation = item.candidate_evaluation_id ? evaluationById.get(item.candidate_evaluation_id) : null;
    return evaluation ? [evaluation] : [];
  }));
  const all = [...baselineEvaluations, ...candidateEvaluations];
  const candidateTrace = candidateEvaluations[0] ? traceById.get(candidateEvaluations[0].trace_id) ?? null : null;
  const baselineTrace = baselineEvaluations[0] ? traceById.get(baselineEvaluations[0].trace_id) ?? null : null;
  const categories = Array.from(
    new Set(all.map((evaluation) => evaluatorInfo(evaluation.evaluator_name).category))
  );
  const title =
    titleFromTrace(candidateTrace ?? baselineTrace) ??
    candidateEvaluations[0]?.label ??
    baselineEvaluations[0]?.label ??
    "Behavioral test case";
  const baselineScore = averageEvaluationScore(baselineEvaluations);
  const candidateScore = averageEvaluationScore(candidateEvaluations);
  const regressedItem = items.find((item) => item.classification === "REGRESSED");
  return {
    key,
    title,
    summary: caseSummary(items),
    baselineEvaluations,
    candidateEvaluations,
    primaryEvaluation: candidateEvaluations.find((evaluation) => !evaluation.passed) ?? candidateEvaluations[0] ?? baselineEvaluations[0] ?? null,
    failedEvaluations: candidateEvaluations.filter((evaluation) => !evaluation.passed),
    categories,
    baselinePassed: baselineEvaluations.length > 0 && baselineEvaluations.every((evaluation) => evaluation.passed),
    candidatePassed: candidateEvaluations.length > 0 && candidateEvaluations.every((evaluation) => evaluation.passed),
    baselineScore,
    candidateScore,
    scoreDelta: (candidateScore ?? 0) - (baselineScore ?? 0),
    baselineTrace,
    candidateTrace,
    failureAnalysis: regressedItem?.failure_analysis ?? null
  };
}

function uniqueEvaluations(items: EvaluationResult[]) {
  return [...new Map(items.map((item) => [item.id, item])).values()];
}

function averageEvaluationScore(items: EvaluationResult[]): number | null {
  const values = items.map((item) => numeric(item.score)).filter((value): value is number => value !== null);
  return values.length ? values.reduce((total, value) => total + value, 0) / values.length : null;
}

function caseSummary(items: CaseComparison[]): string {
  const regressed = items.filter((item) => item.classification === "REGRESSED").length;
  const improved = items.filter((item) => item.classification === "IMPROVED").length;
  if (regressed && improved) return `${regressed} check(s) became worse and ${improved} improved in the candidate.`;
  if (regressed) return `${regressed} check(s) worked better in the baseline than in the candidate.`;
  if (improved) return `${improved} check(s) improved in the candidate.`;
  if (items.some((item) => item.classification === "NOT_COMPARABLE")) return "One side is missing matching evaluation evidence.";
  return "The paired checks produced equivalent evidence.";
}

function mergeChanges(left: ChangeItem[], right: ChangeItem[]): ChangeItem[] {
  return [...new Map([...left, ...right].map((change) => [`${change.label}:${change.field ?? ""}`, change])).values()];
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
          <div key={`${change.label}:${change.field ?? ""}`} className="px-4 py-4">
            <div className="grid gap-3 sm:grid-cols-[8rem_1fr_auto_1fr] sm:items-start">
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
            {configGroupLabel(change.label) === "PROMPT" ? (
              <details className="mt-3 sm:ml-[9rem]">
                <summary className="cursor-pointer text-xs font-medium text-cyan-700">View prompt diff</summary>
                <pre className="mt-2 max-h-64 overflow-auto rounded-xl bg-slate-950 p-3 text-xs leading-5 text-slate-100"><span className="text-red-300">- {change.before}</span>{"\n"}<span className="text-emerald-300">+ {change.after}</span></pre>
              </details>
            ) : null}
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
  tone,
  baselineLabel = "Baseline",
  candidateLabel = "Candidate",
  baselineVersionId,
  candidateVersionId,
  compact = false
}: {
  items: RegressionCase[];
  empty: string;
  tone: "regressed" | "improved" | "unchanged";
  baselineLabel?: string;
  candidateLabel?: string;
  baselineVersionId?: string;
  candidateVersionId?: string;
  compact?: boolean;
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
              <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
                <OutcomeBadge passed={item.baselinePassed} empty={item.baselineEvaluations.length === 0} />
                <span className="font-medium text-slate-600">{baselineLabel}</span>
                <span className="text-slate-300">→</span>
                <OutcomeBadge passed={item.candidatePassed} empty={item.candidateEvaluations.length === 0} />
                <span className="font-medium text-slate-600">{candidateLabel}</span>
              </div>
            </div>
            <div className="text-right">
              <div className={tone === "regressed" ? "text-red-700" : tone === "improved" ? "text-emerald-700" : "text-slate-700"}>
                {scoreMovementLabel(item.scoreDelta)}
              </div>
              <div className="text-xs text-slate-500">average across this case&apos;s checks</div>
            </div>
          </div>

          {!compact ? (
            <>
              <div className="mt-4 overflow-hidden rounded-2xl border border-slate-200">
                <div className="grid grid-cols-[minmax(8rem,0.75fr)_minmax(0,1fr)_minmax(0,1fr)] bg-slate-50 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  <span>Evidence</span>
                  <span>{baselineLabel}</span>
                  <span>{candidateLabel}</span>
                </div>
                <ComparisonRow label="Answer" baseline={traceAnswer(item.baselineTrace)} candidate={traceAnswer(item.candidateTrace)} multiline />
                <ComparisonRow label="Retrieved sources" baseline={listText(retrievalIds(item.baselineTrace))} candidate={listText(retrievalIds(item.candidateTrace))} />
                <ComparisonRow label="Tools" baseline={listText(toolNames(item.baselineTrace))} candidate={listText(toolNames(item.candidateTrace))} />
                {pairedEvaluatorRows(item).map((row) => (
                  <EvaluationComparisonRow key={row.name} name={row.name} baseline={row.baseline} candidate={row.candidate} />
                ))}
              </div>

              <div className="mt-4 rounded-2xl border border-cyan-100 bg-cyan-50/70 p-4 text-sm text-cyan-950">
                <div className="text-xs font-semibold uppercase tracking-wide text-cyan-700">What changed in this case?</div>
                <p className="mt-1 leading-6">{caseDifferenceExplanation(item)}</p>
                <p className="mt-1 text-xs text-cyan-800">This describes observed evidence, not proven causality.</p>
              </div>
            </>
          ) : null}

          <div className="mt-4 flex flex-wrap gap-2">
            {item.candidateTrace ? (
              <Link
                href={traceComparisonHref(item.candidateTrace.id, "candidate", baselineVersionId, candidateVersionId)}
                className="rounded-full bg-ink-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-ink-800"
              >
                Investigate {candidateLabel}
              </Link>
            ) : null}
            {item.baselineTrace && !compact ? (
              <Link
                href={traceComparisonHref(item.baselineTrace.id, "baseline", baselineVersionId, candidateVersionId)}
                className="rounded-full border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Open {baselineLabel}
              </Link>
            ) : null}
            <details className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600 md:w-auto md:min-w-[34rem]">
              <summary className="cursor-pointer font-medium text-slate-700">How scores were calculated</summary>
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
          const reasoning = explainEvaluation(item);
          return (
            <div key={item.id} className="rounded-xl bg-white p-2">
              <div className="flex items-center justify-between gap-2">
                <span>{info.name}</span>
                <EvaluationStatusBadge status={item.status} />
              </div>
              <div className="mt-1 text-slate-700">{reasoning.summary}</div>
              <div className="mt-1 text-slate-500">{reasoning.calculation}</div>
              {reasoning.missing.length ? <div className="mt-1 text-red-700">Missing: {reasoning.missing.join(", ")}</div> : null}
              <div className="mt-1 text-slate-500">{evaluationReliability(item)}</div>
              <details className="mt-1">
                <summary className="cursor-pointer text-slate-500">Advanced details</summary>
                <div className="mt-1 space-y-1 font-mono text-[11px]">
                  <div>raw score: {formatScore(item.score)}</div>
                  <div>threshold: {formatScore(item.threshold)}</div>
                  <div>evaluator: {item.evaluator_name}@{item.evaluator_version}</div>
                  <div>method: {item.method}</div>
                  {item.judge_model ? <div>judge model: {item.judge_model}</div> : null}
                </div>
              </details>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function pairedEvaluatorRows(item: RegressionCase) {
  const baseline = new Map(item.baselineEvaluations.map((evaluation) => [evaluation.evaluator_name, evaluation]));
  const candidate = new Map(item.candidateEvaluations.map((evaluation) => [evaluation.evaluator_name, evaluation]));
  return [...new Set([...baseline.keys(), ...candidate.keys()])].map((name) => ({
    name,
    baseline: baseline.get(name) ?? null,
    candidate: candidate.get(name) ?? null
  }));
}

function EvaluationComparisonRow({ name, baseline, candidate }: { name: string; baseline: EvaluationResult | null; candidate: EvaluationResult | null }) {
  const info = evaluatorInfo(name);
  return (
    <div className="grid grid-cols-[minmax(8rem,0.75fr)_minmax(0,1fr)_minmax(0,1fr)] gap-3 border-t border-slate-100 px-3 py-3 text-sm">
      <div><div className="font-medium text-ink-950">{info.name}</div><div className="text-xs text-slate-500">{info.category}</div></div>
      <EvaluationCell evaluation={baseline} />
      <EvaluationCell evaluation={candidate} />
    </div>
  );
}

function EvaluationCell({ evaluation }: { evaluation: EvaluationResult | null }) {
  if (!evaluation) return <span className="text-slate-400">No evidence</span>;
  return (
    <div>
      <EvaluationStatusBadge status={evaluation.status} />
      <div className="mt-1 text-xs text-slate-600">{Math.round((numeric(evaluation.score) ?? 0) * 100)} / 100</div>
    </div>
  );
}

function ComparisonRow({ label, baseline, candidate, multiline = false }: { label: string; baseline: string | null; candidate: string | null; multiline?: boolean }) {
  return (
    <div className="grid grid-cols-[minmax(8rem,0.75fr)_minmax(0,1fr)_minmax(0,1fr)] gap-3 border-t border-slate-100 px-3 py-3 text-sm">
      <div className="font-medium text-ink-950">{label}</div>
      <div className={`${multiline ? "line-clamp-5 whitespace-pre-wrap" : "break-words"} text-slate-600`}>{baseline ?? "Not recorded"}</div>
      <div className={`${multiline ? "line-clamp-5 whitespace-pre-wrap" : "break-words"} text-slate-600`}>{candidate ?? "Not recorded"}</div>
    </div>
  );
}

function listText(values: string[]): string | null {
  return values.length ? values.join(", ") : null;
}

function caseDifferenceExplanation(item: RegressionCase): string {
  const rows = pairedEvaluatorRows(item);
  const regressions = rows.filter((row) => row.baseline?.passed && row.candidate && !row.candidate.passed);
  const retrieval = regressions.find((row) => evaluatorInfo(row.name).category === "Retrieval");
  if (retrieval?.candidate) {
    const detail = explainEvaluation(retrieval.candidate);
    return `The first supported difference is retrieval evidence. ${detail.summary}${detail.missing.length ? ` Missing: ${detail.missing.join(", ")}.` : ""}`;
  }
  const tool = regressions.find((row) => evaluatorInfo(row.name).category === "Agent Behavior");
  if (tool?.candidate) return `The first supported difference is agent behavior. ${explainEvaluation(tool.candidate).summary}`;
  const answer = regressions.find((row) => evaluatorInfo(row.name).category === "Answer Quality");
  if (answer?.candidate) {
    const detail = explainEvaluation(answer.candidate);
    const retrievalStable = rows.filter((row) => evaluatorInfo(row.name).category === "Retrieval").every((row) => row.baseline?.passed === row.candidate?.passed);
    const prefix = retrievalStable ? "Recorded retrieval checks remained equivalent; the generated answer changed." : "The generated answer no longer met the stored requirement.";
    return `${prefix} ${detail.summary}${detail.missing.length ? ` Missing: ${detail.missing.join(", ")}.` : ""}`;
  }
  if (item.failureAnalysis?.summary) return String(item.failureAnalysis.summary);
  return "AgentGuard found a paired score difference. Open the score calculation and both executions for the supporting evidence.";
}

function traceComparisonHref(traceId: string, role: "baseline" | "candidate", baselineVersionId?: string, candidateVersionId?: string) {
  const params = new URLSearchParams({ role });
  if (baselineVersionId) params.set("baseline_version_id", baselineVersionId);
  if (candidateVersionId) params.set("candidate_version_id", candidateVersionId);
  return `/traces/${traceId}?${params.toString()}`;
}

function scoreMovementLabel(value: string | number | null | undefined): string {
  const parsed = numeric(value);
  if (parsed === null) return "Not available";
  const sign = parsed > 0 ? "+" : "";
  return `${sign}${parsed.toFixed(2)}`;
}
