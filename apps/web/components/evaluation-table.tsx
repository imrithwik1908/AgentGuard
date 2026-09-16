import Link from "next/link";

import { formatDateTime, formatScore } from "@/lib/format";
import type { ApplicationVersion, EvaluationResult, Project, Trace } from "@/lib/types";

import { EvaluationStatusBadge } from "./evaluation-status-badge";

export function EvaluationTable({
  evaluations,
  projects = [],
  versions = [],
  traces = []
}: {
  evaluations: EvaluationResult[];
  projects?: Project[];
  versions?: ApplicationVersion[];
  traces?: Trace[];
}) {
  const projectById = new Map(projects.map((project) => [project.id, project]));
  const versionById = new Map(versions.map((version) => [version.id, version]));
  const traceById = new Map(traces.map((trace) => [trace.id, trace]));

  return (
    <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-panel">
      <table className="w-full min-w-[820px] border-collapse text-left text-sm">
        <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-3">Evaluator</th>
            <th className="px-4 py-3">Trace</th>
            <th className="px-4 py-3">Project</th>
            <th className="px-4 py-3">Version</th>
            <th className="px-4 py-3">Score</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Created</th>
          </tr>
        </thead>
        <tbody>
          {evaluations.map((evaluation) => {
            const trace = traceById.get(evaluation.trace_id);
            const project = projectById.get(evaluation.project_id);
            const version = versionById.get(evaluation.application_version_id);
            return (
              <tr key={evaluation.id} className="border-t border-slate-100 hover:bg-slate-50">
                <td className="px-4 py-3">
                  <div className="font-medium text-ink-950">{evaluation.evaluator_name}</div>
                  <div className="mt-1 text-xs text-slate-500">{evaluation.label ?? "No label"}</div>
                </td>
                <td className="px-4 py-3">
                  <Link className="font-medium text-ink-950 hover:underline" href={`/traces/${evaluation.trace_id}`}>
                    {trace?.name ?? "Open trace"}
                  </Link>
                </td>
                <td className="px-4 py-3 text-slate-700">{project?.name ?? evaluation.project_id}</td>
                <td className="px-4 py-3 text-slate-700">{version?.version ?? evaluation.application_version_id}</td>
                <td className="px-4 py-3 text-slate-700">{formatScore(evaluation.score)}</td>
                <td className="px-4 py-3">
                  <EvaluationStatusBadge status={evaluation.status} />
                </td>
                <td className="px-4 py-3 text-slate-700">{formatDateTime(evaluation.created_at)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
