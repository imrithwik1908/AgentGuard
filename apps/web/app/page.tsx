import Link from "next/link";

import { ApiUnavailable } from "@/components/api-unavailable";
import { ProductStatus } from "@/components/product-status";
import {
  comparePairedVersions,
  listProjects,
  listVersions
} from "@/lib/api";
import { formatPercent } from "@/lib/format";
import {
  deriveReleaseState,
  findDefaultComparisonPair,
  overallLabel,
  summarizeConfigChanges
} from "@/lib/product-intelligence";
import { evaluatorInfo, numeric, type RegressionCase } from "@/lib/product-intelligence";
import type { CaseComparison, PairedVersionComparison } from "@/lib/types";
import { seedDemoAction } from "./actions";

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
  const query = await searchParams;
  const demoError = typeof query.demo_error === "string" ? decodeURIComponent(query.demo_error) : "";
  const demoSeedEnabled = process.env.AGENTGUARD_DEMO_SEED_ENABLED !== "false";

  let projects;
  let versions;
  let comparison: PairedVersionComparison | null = null;
  try {
    projects = await listProjects();
    versions = (await Promise.all(projects.map((project) => listVersions(project.id)))).flat();
    const defaultPair = findDefaultComparisonPair(projects, versions);
    if (defaultPair) {
      comparison = await comparePairedVersions(defaultPair.baseline.id, defaultPair.candidate.id);
    }
  } catch (error) {
    return (
      <div className="space-y-6">
        <ProductStatus />
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
  const regressionCount = buckets.regressed.length;
  const improvementCount = buckets.improved.length;
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
    <div className="space-y-6">
      <section className={`rounded-2xl border p-7 shadow-panel ${decisionStyle(label)}`}>
          <div className="text-xs font-medium uppercase tracking-[0.22em] opacity-70">
            Latest candidate signal
          </div>
          <div className="mt-4 flex flex-wrap items-start justify-between gap-4">
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
            {pair ? (
              <div className="rounded-full bg-white/70 px-4 py-2 text-sm font-medium shadow-sm">
                {regressionCount} {regressionCount === 1 ? "regression" : "regressions"} · {improvementCount} {improvementCount === 1 ? "improvement" : "improvements"}
              </div>
            ) : null}
          </div>

          <div className="mt-6 grid gap-3 border-y border-current/10 py-4 md:grid-cols-3">
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

          <div className="mt-6 flex flex-wrap gap-3">
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
            {demoSeedEnabled ? (
              <form action={seedDemoAction}>
                <button className="rounded-full border border-slate-300 bg-white/75 px-5 py-2.5 text-sm font-medium text-ink-950 hover:border-cyan-400">
                  Load demo data
                </button>
              </form>
            ) : null}
          </div>
          {demoError ? (
            <div className="mt-4 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
              {demoError}
            </div>
          ) : null}
      </section>

      {pair ? <section className="border-y border-slate-200 py-5">
          <div className="text-xs font-medium uppercase tracking-[0.2em] text-cyan-700">
            Observed changes
          </div>
          <div className="mt-3 flex flex-wrap gap-3">
            {changes.slice(0, 3).map((change) => (
              <div key={`${change.label}:${change.field ?? ""}`} className="min-w-56 border-l-2 border-cyan-500 py-1 pl-3">
                <div className="text-sm font-medium text-ink-950">{change.label}</div>
                <div className="mt-1 text-xs text-slate-600">
                  {change.evidence === "observed"
                    ? `${change.before} → ${change.after}`
                    : "No stored configuration difference yet."}
                </div>
              </div>
            ))}
          </div>
          <p className="mt-3 text-xs leading-5 text-slate-500">
            These settings changed alongside the result; they are not proof of causality.
          </p>
      </section> : null}
    </div>
  );
}

function SignalMetric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="px-4 py-2 first:pl-0">
      <div className="text-xs font-medium uppercase tracking-wide opacity-60">{label}</div>
      <div className="mt-2 text-2xl font-semibold">{value}</div>
      <div className="mt-1 text-xs opacity-70">{detail}</div>
    </div>
  );
}
