import Link from "next/link";

import { formatDateTime, formatDuration } from "@/lib/format";
import type { ApplicationVersion, EvaluationResult, Project, Trace } from "@/lib/types";

import { StatusBadge } from "./status-badge";

function runTitle(trace: Trace): string {
  if (trace.input && typeof trace.input === "object" && !Array.isArray(trace.input)) {
    const question = trace.input.question;
    if (typeof question === "string" && question.trim()) return question;
  }
  return trace.name;
}

export function TraceTable({
  traces,
  projects = [],
  versions = [],
  evaluations = []
}: {
  traces: Trace[];
  projects?: Project[];
  versions?: ApplicationVersion[];
  evaluations?: EvaluationResult[];
}) {
  const projectById = new Map(projects.map((project) => [project.id, project]));
  const versionById = new Map(versions.map((version) => [version.id, version]));
  const failedEvaluationsByTrace = new Map<string, number>();
  for (const evaluation of evaluations) {
    if (!evaluation.passed) {
      failedEvaluationsByTrace.set(
        evaluation.trace_id,
        (failedEvaluationsByTrace.get(evaluation.trace_id) ?? 0) + 1
      );
    }
  }

  return (
    <div className="overflow-hidden border-y border-slate-200 bg-white">
      <div className="hidden grid-cols-[minmax(0,1.8fr)_minmax(9rem,0.7fr)_minmax(8rem,0.6fr)_minmax(8rem,0.6fr)_auto] gap-4 bg-slate-50 px-4 py-3 text-xs font-semibold text-slate-500 md:grid">
        <span>Scenario</span><span>Version</span><span>Execution</span><span>Behavior</span><span>Time</span>
      </div>
      <div className="divide-y divide-slate-100">
          {traces.map((trace) => {
            const project = projectById.get(trace.project_id);
            const version = versionById.get(trace.application_version_id);
            const failedEvaluations = failedEvaluationsByTrace.get(trace.id) ?? 0;
            return (
              <div key={trace.id} className="grid gap-3 px-4 py-4 transition hover:bg-slate-50 md:grid-cols-[minmax(0,1.8fr)_minmax(9rem,0.7fr)_minmax(8rem,0.6fr)_minmax(8rem,0.6fr)_auto] md:items-center md:gap-4">
                <div className="min-w-0">
                  <Link className="font-medium text-ink-950 hover:underline" href={`/traces/${trace.id}`}>
                    {runTitle(trace)}
                  </Link>
                  <div className="mt-1 text-xs text-slate-500">{project?.name ?? "Project"} · {formatDateTime(trace.started_at)}</div>
                </div>
                <div className="text-sm font-medium text-slate-700">{version?.version ?? "Unknown version"}</div>
                <div>
                  <span className="mr-2 text-xs text-slate-400 md:hidden">Execution</span>
                  <StatusBadge status={trace.status === "OK" ? "OK" : trace.status} />
                </div>
                <div>
                  <span className="mr-2 text-xs text-slate-400 md:hidden">Behavior</span>
                  {failedEvaluations > 0 ? (
                    <span className="rounded-full bg-red-50 px-2 py-1 text-xs font-medium text-red-700">
                      {failedEvaluations} failed check{failedEvaluations === 1 ? "" : "s"}
                    </span>
                  ) : evaluations.some((evaluation) => evaluation.trace_id === trace.id) ? (
                    <span className="rounded-full bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700">Checks passed</span>
                  ) : (
                    <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">Not evaluated</span>
                  )}
                </div>
                <div className="text-sm text-slate-600">{formatDuration(trace.duration_ms)}</div>
              </div>
            );
          })}
      </div>
    </div>
  );
}
