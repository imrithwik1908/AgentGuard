import Link from "next/link";

import { ApiUnavailable } from "@/components/api-unavailable";
import { EvaluationStatusBadge } from "@/components/evaluation-status-badge";
import {
  compareVersions,
  listEvaluations,
  listProjects,
  listTraces,
  listVersions
} from "@/lib/api";
import { formatPercent, formatScore } from "@/lib/format";
import {
  classifyEvaluationPairs,
  deriveReleaseState,
  findComparisonPair,
  findDefaultComparisonPair,
  type RegressionCase,
  summarizeConfigChanges
} from "@/lib/product-intelligence";
import { evaluatorInfo, numeric } from "@/lib/product-intelligence";
import type { ApplicationVersion, EvaluationResult, Project } from "@/lib/types";

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
  let comparison = null;
  try {
    if (pair) {
      comparison = await compareVersions(pair.baseline.id, pair.candidate.id);
    }
  } catch (error) {
    return (
      <ApiUnavailable
        title="Release comparison failed"
        detail={error instanceof Error ? error.message : String(error)}
      />
    );
  }

  const buckets = pair
    ? classifyEvaluationPairs({
        evaluations: evaluations.items,
        traces: traces.items,
        baselineVersionId: pair.baseline.id,
        candidateVersionId: pair.candidate.id
      })
    : { regressed: [], improved: [], unchanged: [], notComparable: [] };
  const releaseState = deriveReleaseState(buckets, comparison);
  const changes = pair ? summarizeConfigChanges(pair.baseline, pair.candidate) : [];
  const comparedCount = buckets.regressed.length + buckets.improved.length + buckets.unchanged.length;

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
          </div>
          {pair ? (
            <div className="rounded-2xl bg-white/70 p-4 shadow-sm">
              <div className="text-xs uppercase tracking-wide opacity-60">Compared evidence</div>
              <div className="mt-2 text-3xl font-semibold">{comparedCount}</div>
              <p className="mt-2 max-w-sm text-sm leading-5 opacity-75">
                Behavioral test cases evaluated in both baseline and candidate.
              </p>
            </div>
          ) : null}
        </div>

        <div className="mt-6 grid gap-3 md:grid-cols-4">
          <Metric label="Regressed" value={buckets.regressed.length} detail="Paired cases worse in candidate" />
          <Metric label="Improved" value={buckets.improved.length} detail="Candidate fixed or improved" />
          <Metric label="Unchanged" value={buckets.unchanged.length} detail="Equivalent paired checks" />
          <Metric label="Not comparable" value={buckets.notComparable.length} detail="Missing evidence from one side" />
        </div>
      </section>

      <section className="overflow-hidden rounded-[2rem] border border-slate-200 bg-white shadow-panel">
        <div className="border-b border-slate-200 bg-slate-50/80 p-5">
          <h2 className="text-lg font-semibold text-ink-950">Compare versions</h2>
          <p className="mt-1 text-sm text-slate-600">
            AgentGuard can compare stored evaluation results now. Semantic, retrieval, and tool
            causality will appear here when those evaluators exist.
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

      {comparison ? (
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
            <div className="mt-4 space-y-3">
              {changes.map((change) => (
                <div key={change.label} className="rounded-2xl bg-white/75 p-3">
                  <div className="text-sm font-medium text-ink-950">{change.label}</div>
                  <div className="mt-2 grid gap-1 text-xs text-slate-600">
                    <div>Baseline: {change.before}</div>
                    <div>Candidate: {change.after}</div>
                  </div>
                </div>
              ))}
            </div>
            <p className="mt-4 text-xs leading-5 text-slate-500">
              These are observed stored configuration differences only. Behavioral causality is not
              inferred unless a specific evaluator provides evidence.
            </p>
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

function Metric({ label, value, detail }: { label: string; value: React.ReactNode; detail: string }) {
  return (
    <div className="rounded-2xl bg-white/70 p-4 shadow-sm">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-ink-950">{value}</div>
      <div className="mt-1 text-xs text-slate-600">{detail}</div>
    </div>
  );
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
            <details className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm text-slate-600">
              <summary className="cursor-pointer">Evaluation evidence</summary>
              <div className="mt-3 grid gap-3 pb-2 text-xs leading-5 lg:grid-cols-2">
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
