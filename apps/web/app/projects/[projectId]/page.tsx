import Link from "next/link";

import { ApiUnavailable } from "@/components/api-unavailable";
import { EmptyState } from "@/components/empty-state";
import { MetricCard } from "@/components/metric-card";
import { StatusBadge } from "@/components/status-badge";
import { TraceTable } from "@/components/trace-table";
import { getProject, listTraces, listVersions } from "@/lib/api";
import { formatDateTime } from "@/lib/format";

import { createVersionAction } from "../actions";

export default async function ProjectDetailPage({
  params,
  searchParams
}: {
  params: Promise<{ projectId: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { projectId } = await params;
  const query = await searchParams;
  const versionError = typeof query.version_error === "string" ? query.version_error : "";
  let project;
  let versions;
  let traces;
  try {
    project = await getProject(projectId);
    [versions, traces] = await Promise.all([
      listVersions(project.id),
      listTraces({ projectId: project.id, limit: 25 })
    ]);
  } catch (error) {
    return (
      <ApiUnavailable
        title="Project details cannot reach the AgentGuard API"
        detail={error instanceof Error ? error.message : String(error)}
      />
    );
  }
  const okCount = traces.items.filter((trace) => trace.status === "OK").length;
  const errorCount = traces.items.filter((trace) => trace.status === "ERROR").length;
  const createVersionForProject = createVersionAction.bind(null, project.id);

  return (
    <div className="space-y-6">
      <div className="rounded border border-slate-200 bg-white p-5 shadow-panel">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-sm text-slate-500">
              <Link href="/projects" className="hover:underline">
                Projects
              </Link>{" "}
              / {project.slug}
            </div>
            <h1 className="mt-2 text-2xl font-semibold text-ink-950">{project.name}</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
              {project.description ??
                "Register versions of this AI application, run test-suite cases, and compare candidate behavior against a baseline."}
            </p>
          </div>
          <Link
            className="rounded bg-ink-900 px-4 py-2 text-sm font-medium text-white hover:bg-ink-800"
            href={`/traces?project_id=${project.id}`}
          >
            Browse project runs
          </Link>
        </div>
      </div>

      <section className="grid gap-3 md:grid-cols-4">
        <MetricCard label="Versions" value={versions.length} detail="Registered application builds" tone="focus" />
        <MetricCard label="Recent runs" value={traces.total} detail="Stored executions" />
        <MetricCard label="OK" value={okCount} detail="Healthy recent runs" tone="ok" />
        <MetricCard label="Errors" value={errorCount} detail="Runs requiring inspection" tone="error" />
      </section>

      <section className="rounded border border-cyan-200 bg-cyan-50/70 p-4 shadow-panel">
        <h2 className="text-sm font-semibold text-ink-950">How this project gets telemetry</h2>
        <div className="mt-3 grid gap-3 text-sm text-slate-700 lg:grid-cols-3">
          <div>1. Register a version such as <span className="font-mono">v1</span>.</div>
          <div>2. Run the Python demo agent or a test-suite case against that version.</div>
          <div>3. Open a failed run only when you need the timing waterfall and step details.</div>
        </div>
      </section>

      <section className="rounded border border-slate-200 bg-white p-4 shadow-panel">
        <h2 className="text-sm font-semibold text-ink-950">Register application version</h2>
        {versionError ? (
          <div className="mt-3 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
            {versionError}
          </div>
        ) : null}
        <form action={createVersionForProject} className="mt-4 grid gap-3 md:grid-cols-[1fr_0.7fr_1fr_auto]">
          <input
            required
            name="name"
            placeholder="Initial local version"
            className="rounded border border-slate-300 px-3 py-2 text-sm outline-none focus:border-ink-700"
          />
          <input
            required
            name="version"
            placeholder="v1"
            className="rounded border border-slate-300 px-3 py-2 text-sm outline-none focus:border-ink-700"
          />
          <input
            name="git_commit"
            placeholder="optional git commit"
            className="rounded border border-slate-300 px-3 py-2 text-sm outline-none focus:border-ink-700"
          />
          <button className="rounded bg-ink-900 px-4 py-2 text-sm font-medium text-white hover:bg-ink-800">
            Register
          </button>
        </form>
      </section>

      <section className="rounded border border-slate-200 bg-white shadow-panel">
        <div className="border-b border-slate-200 px-4 py-3">
          <h2 className="text-sm font-semibold text-ink-950">Application versions</h2>
        </div>
        {versions.length === 0 ? (
          <div className="p-4 text-sm text-slate-600">
            No versions registered yet. Create one through the API before running the demo agent.
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {versions.map((version) => (
              <div key={version.id} className="grid gap-2 px-4 py-3 md:grid-cols-[1fr_auto]">
                <div>
                  <div className="font-medium text-ink-950">{version.name}</div>
                  <div className="mt-1 font-mono text-xs text-slate-500">{version.version}</div>
                </div>
                <div className="text-sm text-slate-500">{formatDateTime(version.created_at)}</div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-ink-950">Recent runs</h2>
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <StatusBadge status="OK" />
            <StatusBadge status="ERROR" />
          </div>
        </div>
        {traces.items.length === 0 ? (
          <EmptyState
            title="No runs yet"
            description="Run the demo agent or a test-suite case after creating an application version to populate this project."
          />
        ) : (
          <TraceTable traces={traces.items} projects={[project]} versions={versions} />
        )}
      </section>
    </div>
  );
}
