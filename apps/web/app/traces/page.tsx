import { ApiUnavailable } from "@/components/api-unavailable";
import { EmptyState } from "@/components/empty-state";
import { TraceTable } from "@/components/trace-table";
import { listEvaluations, listProjects, listTraces, listVersions } from "@/lib/api";
import type { RunStatus, Trace } from "@/lib/types";

function dateFilter(trace: Trace, from?: string, to?: string): boolean {
  const started = new Date(trace.started_at).getTime();
  if (from && started < new Date(from).getTime()) return false;
  if (to && started > new Date(to).getTime()) return false;
  return true;
}

function searchableText(trace: Trace): string {
  const input = trace.input && typeof trace.input === "object" && !Array.isArray(trace.input)
    ? trace.input.question
    : null;
  return `${trace.name} ${typeof input === "string" ? input : ""}`.toLowerCase();
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
  const search = typeof query.q === "string" ? query.q.trim() : "";

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
  const visibleTraces = traces.items.filter(
    (trace) => dateFilter(trace, from, to) && (!search || searchableText(trace).includes(search.toLowerCase()))
  );
  const hasFilters = Boolean(projectId || versionId || status || from || to || search);

  return (
    <div className="space-y-6">
      <section className="page-intro">
        <div className="text-xs font-semibold uppercase tracking-wide text-cyan-700">Investigate</div>
        <h1 className="mt-2 text-2xl font-semibold text-ink-950">Runs</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
          One row is one application execution. Open a run to see its answer, evidence, checks, and detailed steps.
        </p>
      </section>

      <form className="tool-panel flex flex-wrap items-center gap-2 p-3">
        <label className="min-w-52 flex-1">
          <span className="sr-only">Search runs</span>
          <input
            name="q"
            type="search"
            defaultValue={search}
            placeholder="Search runs..."
            className="w-full rounded-lg border border-slate-200 bg-slate-50/70 px-3 py-2 text-sm text-ink-950 outline-none transition focus:border-cyan-500 focus:bg-white"
          />
        </label>
        <label>
          <span className="sr-only">Project</span>
          <select
            name="project_id"
            defaultValue={projectId}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-ink-950"
          >
            <option value="">All projects</option>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="sr-only">Version</span>
          <select
            name="version_id"
            defaultValue={versionId}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-ink-950"
          >
            <option value="">All versions</option>
            {selectedProjectVersions.map((version) => (
              <option key={version.id} value={version.id}>
                {version.version}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="sr-only">Execution status</span>
          <select
            name="status"
            defaultValue={status}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-ink-950"
          >
            <option value="">Any execution</option>
            <option value="OK">Completed</option>
            <option value="ERROR">Runtime error</option>
            <option value="UNSET">Unknown</option>
          </select>
        </label>
        <label>
          <span className="sr-only">From date</span>
          <input
            name="from"
            type="datetime-local"
            defaultValue={from}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-ink-950"
          />
        </label>
        <label>
            <span className="sr-only">To date</span>
            <input
              name="to"
              type="datetime-local"
              defaultValue={to}
              className="min-w-0 rounded-lg border border-slate-300 px-3 py-2 text-sm text-ink-950"
            />
        </label>
        <button className="rounded-lg bg-ink-900 px-4 py-2 text-sm font-medium text-white">Filter</button>
        <span className="ml-auto px-2 text-sm text-slate-500">{visibleTraces.length} runs</span>
      </form>

      {hasFilters ? (
        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600">
          <span>Showing a filtered view.</span>
          <a href="/traces" className="font-medium text-cyan-800 hover:underline">Clear every filter</a>
        </div>
      ) : null}

      {visibleTraces.length === 0 ? (
        <EmptyState
          title="No runs match these filters"
          description="Adjust the filters or submit runs from an instrumented application."
        />
      ) : (
        <TraceTable traces={visibleTraces} projects={projects} versions={versions} evaluations={evaluations.items} />
      )}
    </div>
  );
}
