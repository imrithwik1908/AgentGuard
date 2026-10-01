import Link from "next/link";

import { ApplicationArchitecture } from "@/components/application-architecture";
import { ApiUnavailable } from "@/components/api-unavailable";
import {
  comparePairedVersions,
  listEvaluations,
  listProjects,
  listTraces,
  listVersions
} from "@/lib/api";
import {
  architectureLayerForDifference,
  firstSupportedDifference,
  observedApplicationArchitecture
} from "@/lib/evaluation-explanations";
import { formatPercent } from "@/lib/format";
import {
  deriveReleaseState,
  findDefaultComparisonPair,
  overallLabel,
  summarizeConfigChanges
} from "@/lib/product-intelligence";
import { evaluatorInfo, numeric, type RegressionCase } from "@/lib/product-intelligence";
import type { CaseComparison, EvaluationResult, PairedVersionComparison, Trace } from "@/lib/types";

function decisionStyle(label: string) {
  if (label === "REGRESSION") return "border-red-200 bg-red-50 text-red-950";
  if (label === "IMPROVED") return "border-emerald-200 bg-emerald-50 text-emerald-950";
  if (label === "REVIEW") return "border-amber-200 bg-amber-50 text-amber-950";
  return "border-slate-200 bg-slate-50 text-slate-950";
}

function simpleCase(item: CaseComparison): RegressionCase {
  const info = evaluatorInfo(item.evaluator_name);
  return {
    key: `${item.dataset_case_id ?? "unknown"}:${item.evaluator_name}`,
    title: item.dataset_case_id ? "Behavioral test case" : "Unpaired check",
    summary: item.explanation,
    baselineEvaluations: [],
    candidateEvaluations: [],
    primaryEvaluation: null,
    failedEvaluations: [],
    categories: [info.category],
    baselinePassed: item.baseline_status === "PASS",
    candidatePassed: item.candidate_status === "PASS",
    baselineScore: numeric(item.baseline_score),
    candidateScore: numeric(item.candidate_score),
    scoreDelta: (numeric(item.candidate_score) ?? 0) - (numeric(item.baseline_score) ?? 0),
    baselineTrace: null,
    candidateTrace: null,
    failureAnalysis: item.failure_analysis
  };
}

export default async function HomePage({
  searchParams
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  await searchParams;

  let projects;
  let versions;
  let comparison: PairedVersionComparison | null = null;
  let latestCandidateTrace: Trace | null = null;
  let candidateArchitectureTraces: Trace[] = [];
  let latestCandidateEvaluations: EvaluationResult[] = [];
  try {
    projects = await listProjects();
    versions = (await Promise.all(projects.map((project) => listVersions(project.id)))).flat();
    const defaultPair = findDefaultComparisonPair(projects, versions);
    if (defaultPair) {
      const [paired, candidateTraces, candidateEvaluations] = await Promise.all([
        comparePairedVersions(defaultPair.baseline.id, defaultPair.candidate.id),
        listTraces({ versionId: defaultPair.candidate.id, limit: 25 }),
        listEvaluations({ versionId: defaultPair.candidate.id, limit: 200 })
      ]);
      comparison = paired;
      latestCandidateTrace = candidateTraces.items[0] ?? null;
      candidateArchitectureTraces = candidateTraces.items;
      latestCandidateEvaluations = latestCandidateTrace
        ? candidateEvaluations.items.filter((item) => item.trace_id === latestCandidateTrace?.id)
        : [];
    }
  } catch (error) {
    return (
      <div className="py-8">
        <ApiUnavailable detail={error instanceof Error ? error.message : String(error)} />
      </div>
    );
  }

  const pair = findDefaultComparisonPair(projects, versions);
  const buckets = comparison
    ? {
        regressed: comparison.regressed.map(simpleCase),
        improved: comparison.improved.map(simpleCase),
        unchanged: comparison.unchanged.map(simpleCase),
        notComparable: comparison.not_comparable.map(simpleCase)
      }
    : { regressed: [], improved: [], unchanged: [], notComparable: [] };
  const releaseState = deriveReleaseState(buckets, comparison);
  const label = overallLabel(comparison, releaseState);
  const changes = pair ? summarizeConfigChanges(pair.baseline, pair.candidate) : [];
  const missingCount = buckets.notComparable.length;
  const nextAction = !pair
    ? { label: "Set up a project", href: "/projects" }
    : buckets.regressed.length > 0
      ? {
          label: "Review regressions",
          href: `/releases?baseline_version_id=${pair.baseline.id}&candidate_version_id=${pair.candidate.id}`
        }
      : comparison?.candidate.evaluation_count
        ? {
            label: "Open release decision",
            href: `/releases?baseline_version_id=${pair.baseline.id}&candidate_version_id=${pair.candidate.id}`
          }
        : { label: "Run a test suite", href: "/datasets" };
  return (
    <div className="space-y-10">
      <section className={`overflow-hidden rounded-[1.75rem] border shadow-[0_22px_65px_rgba(15,23,42,0.08)] ${decisionStyle(label)}`}>
        <div className="p-7 sm:p-9">
          <div className="text-xs font-medium uppercase tracking-[0.22em] opacity-70">
            Current release signal
          </div>
          <div className="mt-4 flex flex-wrap items-start justify-between gap-6">
            <div>
              <h1 className="text-3xl font-semibold tracking-normal">{releaseState.title}</h1>
              {pair ? (
                <p className="mt-3 max-w-3xl text-sm leading-6 opacity-80">
                  {pair.project.name}: candidate <strong>{pair.candidate.version}</strong> compared
                  with baseline <strong>{pair.baseline.version}</strong>.
                </p>
              ) : (
                <p className="mt-3 max-w-3xl text-sm leading-6 opacity-80">
                  Create a project, register two versions, and run evaluations to see whether a
                  change improved behavior or introduced regressions.
                </p>
              )}
              <p className="mt-2 max-w-3xl text-sm leading-6 opacity-80">
                {releaseState.explanation}
              </p>
            </div>
            {pair ? <VersionRoute baseline={pair.baseline.version} candidate={pair.candidate.version} /> : null}
          </div>

          <div className="mt-6 flex flex-col divide-y divide-current/10 border-y border-current/10 py-2 md:flex-row md:divide-x md:divide-y-0">
            <SignalMetric
              label="Regressions"
              value={String(buckets.regressed.length)}
              detail="Paired checks that worked better in the baseline"
            />
            <SignalMetric
              label="Improvements"
              value={String(buckets.improved.length)}
              detail="Paired checks that became better in the candidate"
            />
            <SignalMetric
              label="Evaluation coverage"
              value={formatPercent(comparison?.comparison_coverage)}
              detail={`${missingCount} ${missingCount === 1 ? "check is" : "checks are"} still not comparable`}
            />
          </div>

          <div className="mt-7 flex flex-wrap gap-3">
            <Link
              href={nextAction.href}
              className="rounded-full bg-ink-950 px-5 py-2.5 text-sm font-medium text-white hover:bg-ink-800"
            >
              {nextAction.label}
            </Link>
            <Link
              href="/docs"
              className="rounded-full border border-slate-300 bg-white/75 px-5 py-2.5 text-sm font-medium text-ink-950 hover:border-cyan-400"
            >
              SDK quickstart
            </Link>
          </div>
        </div>
      </section>

      {latestCandidateTrace ? (
        <section className="py-2">
          <ApplicationArchitecture
            architecture={observedApplicationArchitecture(candidateArchitectureTraces)}
            highlightedLayer={architectureLayerForDifference(firstSupportedDifference(latestCandidateEvaluations))}
            title={`${pair?.candidate.version ?? "Current version"} system components observed by AgentGuard`}
          />
          <p className="mt-5 max-w-3xl border-l-2 border-cyan-500 pl-4 text-sm leading-6 text-slate-600">
            This component diagram is reconstructed from real SDK spans across recent runs. A highlighted layer is where stored checks first support a difference; it is investigation evidence, not proof that the component caused the outcome.
          </p>
        </section>
      ) : null}

      {pair && changes.length ? (
        <section className="border-t border-slate-200 pt-7">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <div className="text-xs font-medium uppercase tracking-[0.2em] text-cyan-700">Observed application changes</div>
              <h2 className="mt-2 text-xl font-semibold text-ink-950">What changed between the versions</h2>
            </div>
            <Link href={`/releases?baseline_version_id=${pair.baseline.id}&candidate_version_id=${pair.candidate.id}`} className="text-sm font-medium text-cyan-800 hover:underline">See the full comparison</Link>
          </div>
          <div className="mt-5 divide-y divide-slate-200 border-y border-slate-200">
            {changes.slice(0, 4).map((change) => (
              <div key={`${change.label}:${change.field ?? ""}`} className="grid gap-2 py-4 sm:grid-cols-[12rem_1fr_auto_1fr] sm:items-center">
                <div className="text-sm font-medium text-ink-950">{change.label}</div>
                <div className="text-sm text-slate-600">{change.before}</div>
                <div className="hidden text-slate-300 sm:block">→</div>
                <div className="text-sm font-medium text-ink-950">{change.after}</div>
              </div>
            ))}
          </div>
          <p className="mt-3 text-xs leading-5 text-slate-500">These settings changed alongside the evaluation result. AgentGuard treats them as investigation context, not proof of causality.</p>
        </section>
      ) : null}
    </div>
  );
}

function VersionRoute({ baseline, candidate }: { baseline: string; candidate: string }) {
  return (
    <div className="flex items-center gap-3 rounded-full bg-white/65 px-4 py-2 text-sm shadow-sm ring-1 ring-black/5">
      <span className="font-medium">{baseline}</span>
      <span className="text-slate-400">→</span>
      <span className="font-semibold">{candidate}</span>
    </div>
  );
}

function SignalMetric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="flex-1 px-4 py-3 first:pl-0">
      <div className="text-xs font-medium uppercase tracking-wide opacity-60">{label}</div>
      <div className="mt-2 text-2xl font-semibold">{value}</div>
      <div className="mt-1 text-xs opacity-70">{detail}</div>
    </div>
  );
}
