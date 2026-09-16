import Link from "next/link";

import { formatDateTime, formatDuration } from "@/lib/format";
import type { ApplicationVersion, Project, Trace } from "@/lib/types";

import { StatusBadge } from "./status-badge";

export function TraceTable({
  traces,
  projects = [],
  versions = []
}: {
  traces: Trace[];
  projects?: Project[];
  versions?: ApplicationVersion[];
}) {
  const projectById = new Map(projects.map((project) => [project.id, project]));
  const versionById = new Map(versions.map((version) => [version.id, version]));

  return (
    <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-panel">
      <table className="w-full min-w-[760px] border-collapse text-left text-sm">
        <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-3">Run</th>
            <th className="px-4 py-3">Project</th>
            <th className="px-4 py-3">Version</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Duration</th>
            <th className="px-4 py-3">Started</th>
          </tr>
        </thead>
        <tbody>
          {traces.map((trace) => {
            const project = projectById.get(trace.project_id);
            const version = versionById.get(trace.application_version_id);
            return (
              <tr key={trace.id} className="border-t border-slate-100 hover:bg-slate-50">
                <td className="px-4 py-3">
                  <Link className="font-medium text-ink-950 hover:underline" href={`/traces/${trace.id}`}>
                    {trace.name}
                  </Link>
                  <div className="mt-1 text-xs text-slate-500">{trace.external_trace_id ?? trace.id}</div>
                </td>
                <td className="px-4 py-3 text-slate-700">{project?.name ?? trace.project_id}</td>
                <td className="px-4 py-3 text-slate-700">{version?.version ?? trace.application_version_id}</td>
                <td className="px-4 py-3">
                  <StatusBadge status={trace.status} />
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
