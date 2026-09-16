import Link from "next/link";

import { ApiUnavailable } from "@/components/api-unavailable";
import { EvaluationStatusBadge } from "@/components/evaluation-status-badge";
import { listEvaluations, listProjects, listTraces, listVersions } from "@/lib/api";
import { formatDateTime, formatScore } from "@/lib/format";
import {
  evaluatorInfo,
  implementedEvaluatorCatalog,
  PLANNED_EVALUATORS
} from "@/lib/product-intelligence";

const CATEGORIES = ["Answer Quality", "Retrieval", "Agent Behavior", "Operational"] as const;

export default async function EvaluationsPage() {
  let evaluations;
  let projects;
  let versions;
  let traces;
  try {
    [evaluations, projects, traces] = await Promise.all([
      listEvaluations({ limit: 100 }),
      listProjects(),
      listTraces({ limit: 100 })
    ]);
    versions = (await Promise.all(projects.map((project) => listVersions(project.id)))).flat();
  } catch (error) {
    return (
      <ApiUnavailable
        title="Evaluations cannot reach the AgentGuard API"
        detail={error instanceof Error ? error.message : String(error)}
      />
    );
  }

  const projectById = new Map(projects.map((project) => [project.id, project]));
  const versionById = new Map(versions.map((version) => [version.id, version]));
  const traceById = new Map(traces.items.map((trace) => [trace.id, trace]));
  const implemented = implementedEvaluatorCatalog();

  return (
    <div className="space-y-8">
      <section className="surface rounded-[2rem] p-6">
        <div className="text-xs font-medium uppercase tracking-[0.22em] text-cyan-700">
          Evaluate
        </div>
        <div className="mt-3 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-3xl font-semibold text-ink-950">What AgentGuard checks</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
              An evaluator is a check that measures whether a run behaved as expected. These checks
              become the evidence AgentGuard uses to compare a baseline with a candidate.
            </p>
          </div>
          <Link
            href="/releases"
            className="rounded-full bg-ink-950 px-5 py-2.5 text-sm font-medium text-white hover:bg-ink-800"
          >
            Open release workflow
          </Link>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-4">
        {CATEGORIES.map((category) => {
          const active = implemented.filter((item) => item.category === category);
          return (
            <div key={category} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-panel">
              <div className="text-sm font-semibold text-ink-950">{category}</div>
              <p className="mt-1 text-xs leading-4 text-slate-500">{categoryDescription(category)}</p>
              <div className="mt-3 space-y-2">
                {active.length > 0 ? (
                  active.map((item) => (
                    <div key={item.name} className="rounded-xl bg-emerald-50 px-3 py-2">
                      <div className="text-sm font-medium text-emerald-950">{item.name}</div>
                      <div className="mt-1 text-xs leading-4 text-emerald-800">{item.description}</div>
                    </div>
                  ))
                ) : (
                  <div className="rounded-xl bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-500">
                    No active checks in this category yet.
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </section>

      <section className="rounded-[2rem] border border-dashed border-slate-300 bg-white/70 p-5">
        <details>
          <summary className="cursor-pointer text-sm font-semibold text-ink-950">
            Coming next: AI-native evaluators
          </summary>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            These are designed into the product direction but are not presented as active results
            until the backend implements them.
          </p>
          <div className="mt-4 grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            {PLANNED_EVALUATORS.map((item) => (
              <div key={item.name} className="rounded-xl bg-slate-50 px-3 py-2">
                <div className="text-sm font-medium text-slate-700">{item.name}</div>
                <div className="mt-1 text-xs leading-4 text-slate-500">{item.description}</div>
              </div>
            ))}
          </div>
        </details>
      </section>

      <section className="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-ink-950">Recent check results</h2>
            <p className="mt-1 text-sm text-slate-600">
              Human names first. Internal evaluator IDs are kept secondary for debugging.
            </p>
          </div>
          <Link className="text-sm font-medium text-ink-800 hover:underline" href="/datasets">
            Run test suites
          </Link>
        </div>

        {evaluations.items.length > 0 ? (
          <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-panel">
            <div className="divide-y divide-slate-100">
              {evaluations.items.map((evaluation) => {
                const info = evaluatorInfo(evaluation.evaluator_name);
                const project = projectById.get(evaluation.project_id);
                const version = versionById.get(evaluation.application_version_id);
                const trace = traceById.get(evaluation.trace_id);
                return (
                  <div key={evaluation.id} className="grid gap-3 p-4 lg:grid-cols-[1fr_auto]">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <EvaluationStatusBadge status={evaluation.status} />
                        <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
                          {info.category}
                        </span>
                      </div>
                      <h3 className="mt-2 text-base font-semibold text-ink-950">
                        {evaluation.label ?? info.name}
                      </h3>
                      <p className="mt-1 text-sm text-slate-600">
                        {project?.name ?? "Project"} · {version?.version ?? "Version"} · Score{" "}
                        {formatScore(evaluation.score)}
                      </p>
                      <details className="mt-2 text-xs text-slate-500">
                        <summary className="cursor-pointer">Advanced evaluator details</summary>
                        <div className="mt-1 font-mono">{evaluation.evaluator_name}</div>
                      </details>
                    </div>
                    <div className="flex items-center gap-3 lg:justify-end">
                      <div className="text-right text-xs text-slate-500">
                        {formatDateTime(evaluation.created_at)}
                      </div>
                      <Link
                        href={`/traces/${evaluation.trace_id}`}
                        className="rounded-full border border-slate-300 px-3 py-1.5 text-sm font-medium text-ink-950 hover:border-cyan-400"
                      >
                        {trace ? "Investigate run" : "Open run"}
                      </Link>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <div className="surface rounded-2xl p-5 text-sm text-slate-600">
            No check results yet. Create a test suite and run cases against a version.
          </div>
        )}
      </section>
    </div>
  );
}

function categoryDescription(category: (typeof CATEGORIES)[number]) {
  if (category === "Answer Quality") return "Checks whether the application answered correctly enough for the case.";
  if (category === "Retrieval") return "Checks whether the application found useful evidence before answering.";
  if (category === "Agent Behavior") return "Checks tools, actions, routing, and guardrail-sensitive behavior.";
  return "Checks runtime behavior such as errors, latency, and inspectable evidence.";
}
