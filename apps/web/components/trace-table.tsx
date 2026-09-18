import Link from "next/link";

import { formatDateTime, formatDuration } from "@/lib/format";
import type { ApplicationVersion, EvaluationResult, Project, Trace } from "@/lib/types";

import { StatusBadge } from "./status-badge";

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
    <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-panel">
      <table className="w-full min-w-[860px] border-collapse text-left text-sm">
        <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-3">Run</th>
            <th className="px-4 py-3">Project</th>
            <th className="px-4 py-3">Version</th>
            <th className="px-4 py-3">Execution</th>
            <th className="px-4 py-3">Evaluation</th>
            <th className="px-4 py-3">Duration</th>
            <th className="px-4 py-3">Started</th>
          </tr>
        </thead>
        <tbody>
          {traces.map((trace) => {
            const project = projectById.get(trace.project_id);
            const version = versionById.get(trace.application_version_id);
            const failedEvaluations = failedEvaluationsByTrace.get(trace.id) ?? 0;
            return (
              <tr key={trace.id} className="border-t border-slate-100 hover:bg-slate-50">
                <td className="px-4 py-3">
                  <Link className="font-medium text-ink-950 hover:underline" href={`/traces/${trace.id}`}>
                    {trace.name}
                  </Link>
                  <div className="mt-1 flex flex-wrap gap-2 text-xs text-slate-500">
                    <span>{trace.spans.length} recorded steps</span>
                    {trace.external_trace_id ? (
                      <span className="font-mono">external {trace.external_trace_id}</span>
                    ) : null}
                  </div>
                </td>
                <td className="px-4 py-3 text-slate-700">{project?.name ?? trace.project_id}</td>
                <td className="px-4 py-3 text-slate-700">{version?.version ?? trace.application_version_id}</td>
                <td className="px-4 py-3">
                  <StatusBadge status={trace.status} />
                </td>
                <td className="px-4 py-3">
                  {failedEvaluations > 0 ? (
                    <span className="rounded-full bg-red-50 px-2 py-1 text-xs font-medium text-red-700">
                      Failed {failedEvaluations} check{failedEvaluations === 1 ? "" : "s"}
                    </span>
                  ) : (
                    <span className="rounded-full bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700">
                      No failed checks
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-slate-700">{formatDuration(trace.duration_ms)}</td>
                <td className="px-4 py-3 text-slate-700">{formatDateTime(trace.started_at)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
