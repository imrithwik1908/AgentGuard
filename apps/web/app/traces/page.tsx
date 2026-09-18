import { ApiUnavailable } from "@/components/api-unavailable";
import { EmptyState } from "@/components/empty-state";
import { MetricCard } from "@/components/metric-card";
import { TraceTable } from "@/components/trace-table";
import { listEvaluations, listProjects, listTraces, listVersions } from "@/lib/api";
import { summarizeTelemetry } from "@/lib/insights";
import type { RunStatus, Trace } from "@/lib/types";

function dateFilter(trace: Trace, from?: string, to?: string): boolean {
  const started = new Date(trace.started_at).getTime();
  if (from && started < new Date(from).getTime()) return false;
  if (to && started > new Date(to).getTime()) return false;
  return true;
}

export default async function TracesPage({
  searchParams
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const query = await searchParams;
  const projectId = typeof query.project_id === "string" ? query.project_id : "";
  const versionId = typeof query.version_id === "string" ? query.version_id : "";
  const status = typeof query.status === "string" ? (query.status as RunStatus | "") : "";
  const from = typeof query.from === "string" ? query.from : "";
  const to = typeof query.to === "string" ? query.to : "";

  let projects;
  let versions;
  let traces;
  let evaluations;
  try {
    projects = await listProjects();
    const versionsByProject = await Promise.all(projects.map((project) => listVersions(project.id)));
    versions = versionsByProject.flat();
    [traces, evaluations] = await Promise.all([
      listTraces({
        projectId: projectId || undefined,
        versionId: versionId || undefined,
        status: status || undefined,
        limit: 100
      }),
      listEvaluations({ limit: 200 })
    ]);
  } catch (error) {
    return (
      <ApiUnavailable
        title="Runs cannot reach the AgentGuard API"
        detail={error instanceof Error ? error.message : String(error)}
      />
    );
  }
  const selectedProjectVersions = projectId
    ? versions.filter((version) => version.project_id === projectId)
    : versions;
  const visibleTraces = traces.items.filter((trace) => dateFilter(trace, from, to));
  const stats = summarizeTelemetry({ projects, versions, traces: visibleTraces });

  return (
    <div className="space-y-6">
      <section className="overflow-hidden rounded-[2rem] border border-slate-200 bg-white shadow-panel">
        <div className="h-1 bg-gradient-to-r from-cyan-500 via-emerald-500 to-slate-900" />
        <div className="p-5">
        <div className="text-xs font-medium uppercase tracking-wide text-cyan-700">Investigation surface</div>
        <h1 className="mt-2 text-2xl font-semibold text-ink-950">Runs</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
          A run is one complete AI application execution. Start here when a regression needs
          debugging, then drill into the trace waterfall and span details only when needed.
        </p>
        </div>
      </section>

      <section className="grid gap-3 md:grid-cols-4">
        <MetricCard label="Visible runs" value={stats.traceCount} detail="Executions matching filters" tone="focus" />
        <MetricCard label="OK" value={stats.okCount} detail="Successful executions" tone="ok" />
        <MetricCard label="Errors" value={stats.errorCount} detail="Runs with captured failures" tone="error" />
        <MetricCard label="Spans" value={stats.spanCount} detail="Operations inside these runs" />
      </section>

      <form className="grid gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-panel md:grid-cols-5">
        <label className="grid gap-1 text-xs font-medium uppercase tracking-wide text-slate-500">
          Project
          <select
            name="project_id"
            defaultValue={projectId}
            className="rounded border border-slate-300 px-3 py-2 text-sm font-normal normal-case tracking-normal text-ink-950"
          >
            <option value="">All projects</option>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-1 text-xs font-medium uppercase tracking-wide text-slate-500">
          Version
          <select
            name="version_id"
            defaultValue={versionId}
            className="rounded border border-slate-300 px-3 py-2 text-sm font-normal normal-case tracking-normal text-ink-950"
          >
            <option value="">All versions</option>
            {selectedProjectVersions.map((version) => (
              <option key={version.id} value={version.id}>
                {version.version}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-1 text-xs font-medium uppercase tracking-wide text-slate-500">
          Status
          <select
            name="status"
            defaultValue={status}
            className="rounded border border-slate-300 px-3 py-2 text-sm font-normal normal-case tracking-normal text-ink-950"
          >
            <option value="">All statuses</option>
            <option value="OK">OK</option>
            <option value="ERROR">ERROR</option>
            <option value="UNSET">UNSET</option>
          </select>
        </label>
        <label className="grid gap-1 text-xs font-medium uppercase tracking-wide text-slate-500">
          From
          <input
            name="from"
            type="datetime-local"
            defaultValue={from}
            className="rounded border border-slate-300 px-3 py-2 text-sm font-normal normal-case tracking-normal text-ink-950"
          />
        </label>
        <div className="flex gap-2">
          <label className="grid min-w-0 flex-1 gap-1 text-xs font-medium uppercase tracking-wide text-slate-500">
            To
            <input
              name="to"
              type="datetime-local"
              defaultValue={to}
              className="min-w-0 rounded border border-slate-300 px-3 py-2 text-sm font-normal normal-case tracking-normal text-ink-950"
            />
          </label>
          <button className="self-end rounded-full bg-ink-900 px-4 py-2 text-sm font-medium text-white">Apply</button>
        </div>
      </form>

      {visibleTraces.length === 0 ? (
        <EmptyState
          title="No runs match these filters"
          description="Adjust the filters or run the demo agent to submit telemetry."
        />
      ) : (
        <TraceTable traces={visibleTraces} projects={projects} versions={versions} evaluations={evaluations.items} />
      )}
    </div>
  );
}
