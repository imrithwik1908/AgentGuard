import Link from "next/link";

import { ApiUnavailable } from "@/components/api-unavailable";
import { ProductStatus } from "@/components/product-status";
import { StatusBadge } from "@/components/status-badge";
import {
  compareVersions,
  listEvaluations,
  listProjects,
  listTraces,
  listVersions
} from "@/lib/api";
import { formatPercent } from "@/lib/format";
import {
  classifyEvaluationPairs,
  deriveReleaseState,
  findDefaultComparisonPair,
  overallLabel,
  summarizeConfigChanges
} from "@/lib/product-intelligence";
import type { EvaluationResult, VersionComparison } from "@/lib/types";
import { seedDemoAction } from "./actions";

function decisionStyle(label: string) {
  if (label === "REGRESSION") return "border-red-200 bg-red-50 text-red-950";
  if (label === "IMPROVED") return "border-emerald-200 bg-emerald-50 text-emerald-950";
  if (label === "REVIEW") return "border-amber-200 bg-amber-50 text-amber-950";
  return "border-slate-200 bg-slate-50 text-slate-950";
}

export default async function HomePage({
  searchParams
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const query = await searchParams;
  const demoError = typeof query.demo_error === "string" ? decodeURIComponent(query.demo_error) : "";

  let projects;
  let versions;
  let traces;
  let evaluations: { items: EvaluationResult[] } = { items: [] };
  let comparison: VersionComparison | null = null;
  try {
    projects = await listProjects();
    versions = (await Promise.all(projects.map((project) => listVersions(project.id)))).flat();
    [traces, evaluations] = await Promise.all([
      listTraces({ limit: 100 }),
      listEvaluations({ limit: 200 })
    ]);
    const defaultPair = findDefaultComparisonPair(projects, versions);
    if (defaultPair) {
      comparison = await compareVersions(defaultPair.baseline.id, defaultPair.candidate.id);
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
  const buckets = pair
    ? classifyEvaluationPairs({
        evaluations: evaluations.items,
        traces: traces.items,
        baselineVersionId: pair.baseline.id,
        candidateVersionId: pair.candidate.id
      })
    : { regressed: [], improved: [], unchanged: [], notComparable: [] };
  const releaseState = deriveReleaseState(buckets, comparison);
  const label = overallLabel(comparison, releaseState);
  const changes = pair ? summarizeConfigChanges(pair.baseline, pair.candidate) : [];
  const recentFailure = traces.items.find((trace) => trace.status === "ERROR") ?? null;
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
  const promiseChecklist = [
    {
      label: "Inspect how an AI application behaved",
      detail: `${traces.items.length} runs recorded with trace/step evidence.`,
      ready: traces.items.length > 0,
      href: "/traces"
    },
    {
      label: "Evaluate representative cases",
      detail: `${evaluations.items.length} stored check results across active projects.`,
      ready: evaluations.items.length > 0,
      href: "/evaluations"
    },
    {
      label: "Compare baseline against candidate",
      detail: pair
        ? `${pair.baseline.version} is being compared with ${pair.candidate.version}.`
        : "Create at least two versions in one project.",
      ready: Boolean(pair),
      href: "/releases"
    },
    {
      label: "Catch regressions before release",
      detail:
        buckets.regressed.length > 0
          ? `${buckets.regressed.length} regressed cases found.`
          : "No paired regressions found in the current evidence.",
      ready: Boolean(pair && comparison),
      href: "/releases"
    },
    {
      label: "Make an evidence-backed release decision",
      detail: releaseState.title,
      ready: releaseState.state === "PASS" || releaseState.state.startsWith("BLOCK"),
      href: "/releases"
    }
  ];

  return (
    <div className="space-y-6">
      <section className="grid gap-5 lg:grid-cols-[minmax(0,1.3fr)_minmax(320px,0.7fr)]">
        <div className={`rounded-[2rem] border p-7 shadow-panel ${decisionStyle(label)}`}>
          <div className="text-xs font-medium uppercase tracking-[0.22em] opacity-70">
            Latest candidate signal
          </div>
          <div className="mt-4 flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="text-4xl font-semibold tracking-normal">{releaseState.title}</h1>
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
                {buckets.regressed.length} regressions · {buckets.improved.length} improvements
              </div>
            ) : null}
          </div>

          <div className="mt-6 grid gap-3 md:grid-cols-3">
            <SignalMetric
              label="Regressions"
              value={String(buckets.regressed.length)}
              detail="Cases that worked better in the baseline"
            />
            <SignalMetric
              label="Improvements"
              value={String(buckets.improved.length)}
              detail="Cases that became better in the candidate"
            />
            <SignalMetric
              label="Evaluation coverage"
              value={formatPercent(comparison?.candidate.pass_rate)}
              detail={`${buckets.notComparable.length} cases still not comparable`}
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
            <form action={seedDemoAction}>
              <button className="rounded-full border border-slate-300 bg-white/75 px-5 py-2.5 text-sm font-medium text-ink-950 hover:border-cyan-400">
                Load demo data
              </button>
            </form>
          </div>
          {demoError ? (
            <div className="mt-4 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
              {demoError}
            </div>
          ) : null}
        </div>

        <aside className="surface rounded-[2rem] p-5">
          <div className="text-xs font-medium uppercase tracking-[0.2em] text-cyan-700">
            Start here
          </div>
          <h2 className="mt-2 text-xl font-semibold text-ink-950">One workflow, five steps</h2>
          <div className="mt-4 space-y-2">
            {[
              ["Instrument", "Connect the SDK to your AI app."],
              ["Test", "Run representative cases."],
              ["Evaluate", "Check expected behavior."],
              ["Investigate", "Open run details only for failures."],
              ["Release", "Ship or block with evidence."]
            ].map(([verb, detail], index) => (
              <div key={verb} className="flex gap-3 rounded-2xl bg-white/75 p-3">
                <div className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-ink-950 text-xs font-semibold text-white">
                  {index + 1}
                </div>
                <div>
                  <div className="text-sm font-semibold text-ink-950">{verb}</div>
                  <div className="text-sm text-slate-600">{detail}</div>
                </div>
              </div>
            ))}
          </div>
        </aside>
      </section>

      <section className="grid gap-4 lg:grid-cols-[1fr_1fr]">
        <div className="surface rounded-[2rem] p-5 lg:col-span-2">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="text-xs font-medium uppercase tracking-[0.2em] text-cyan-700">
                Promise checklist
              </div>
              <h2 className="mt-2 text-xl font-semibold text-ink-950">
                Is AgentGuard delivering the LinkedIn promise?
              </h2>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
                The goal is not to be a generic log viewer. AgentGuard should show what changed,
                what got better or worse, why there is evidence, and whether the candidate is safe to ship.
              </p>
            </div>
            <Link
              className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
              href="/docs"
            >
              See how to use it
            </Link>
          </div>
          <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
            {promiseChecklist.map((item) => (
              <Link
                key={item.label}
                href={item.href}
                className={`rounded-2xl border p-4 transition hover:-translate-y-0.5 ${
                  item.ready
                    ? "border-emerald-200 bg-emerald-50/70"
                    : "border-amber-200 bg-amber-50/70"
                }`}
              >
                <div
                  className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${
                    item.ready ? "bg-emerald-100 text-emerald-900" : "bg-amber-100 text-amber-900"
                  }`}
                >
                  {item.ready ? "Working" : "Needs data"}
                </div>
                <div className="mt-3 text-sm font-semibold text-ink-950">{item.label}</div>
                <div className="mt-2 text-xs leading-5 text-slate-600">{item.detail}</div>
              </Link>
            ))}
          </div>
        </div>

        <div className="surface rounded-[2rem] p-5">
          <div className="text-xs font-medium uppercase tracking-[0.2em] text-cyan-700">
            What changed?
          </div>
          <div className="mt-3 grid gap-2">
            {changes.slice(0, 3).map((change) => (
              <div key={change.label} className="rounded-2xl bg-white/75 p-3">
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
            Observed config differences are facts, not causal claims.
          </p>
        </div>

        <div className="surface rounded-[2rem] p-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-xs font-medium uppercase tracking-[0.2em] text-cyan-700">
                Needs attention
              </div>
              <h2 className="mt-2 text-xl font-semibold text-ink-950">
                {recentFailure ? recentFailure.name : "No recent failed runs"}
              </h2>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                {recentFailure
                  ? String(recentFailure.error?.message ?? "A run recorded an ERROR status.")
                  : "When evaluations or runs fail, AgentGuard will link you to the investigation surface here."}
              </p>
            </div>
            {recentFailure ? <StatusBadge status="ERROR" /> : <StatusBadge status="OK" />}
          </div>
          <div className="mt-5">
            <Link
              href={recentFailure ? `/traces/${recentFailure.id}` : "/traces"}
              className="rounded-full bg-ink-950 px-4 py-2 text-sm font-medium text-white hover:bg-ink-800"
            >
              {recentFailure ? "Investigate run" : "View runs"}
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}

function SignalMetric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-2xl bg-white/70 p-4 shadow-sm">
      <div className="text-xs font-medium uppercase tracking-wide opacity-60">{label}</div>
      <div className="mt-2 text-2xl font-semibold">{value}</div>
      <div className="mt-1 text-xs opacity-70">{detail}</div>
    </div>
  );
}
