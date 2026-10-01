import Link from "next/link";

import { ApiUnavailable } from "@/components/api-unavailable";
import { EmptyState } from "@/components/empty-state";
import { listProjects } from "@/lib/api";
import { formatDateTime } from "@/lib/format";

import { createProjectAction } from "./actions";

export default async function ProjectsPage({
  searchParams
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const query = await searchParams;
  const projectError = typeof query.project_error === "string" ? query.project_error : "";
  let projects;
  try {
    projects = await listProjects();
  } catch (error) {
    return <ApiUnavailable detail={error instanceof Error ? error.message : String(error)} />;
  }

  return (
    <div className="space-y-6">
      <div className="page-intro">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-cyan-700">Workspace setup</div>
            <h1 className="mt-2 text-2xl font-semibold text-ink-950">Setup</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
              A project is one AI application, such as a support bot, research agent, RAG pipeline,
              or tool-using workflow. Versions let you separate behavior by prompt, model, retrieval,
              code, or orchestration changes.
            </p>
          </div>
          <Link
            className="rounded border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            href="/traces"
          >
            Browse runs
          </Link>
        </div>
      </div>

      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-ink-950">Project registry</h2>
          <p className="mt-1 text-sm text-slate-600">Create or open the application you want to observe.</p>
        </div>
      </div>

      <section className="tool-panel p-5">
        <h3 className="text-sm font-semibold text-ink-950">Create project</h3>
        {projectError ? (
          <div className="mt-3 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
            {projectError}
          </div>
        ) : null}
        <form action={createProjectAction} className="mt-4 grid gap-3 md:grid-cols-[1fr_0.8fr_1.5fr_auto]">
          <input
            required
            name="name"
            placeholder="Research Agent"
            className="rounded border border-slate-300 px-3 py-2 text-sm outline-none focus:border-ink-700"
          />
          <input
            required
            name="slug"
            placeholder="research-agent"
            pattern="^[a-z0-9]+(?:-[a-z0-9]+)*$"
            className="rounded border border-slate-300 px-3 py-2 text-sm outline-none focus:border-ink-700"
          />
          <input
            name="description"
            placeholder="Meeting notes assistant"
            className="rounded border border-slate-300 px-3 py-2 text-sm outline-none focus:border-ink-700"
          />
          <button className="rounded bg-ink-900 px-4 py-2 text-sm font-medium text-white hover:bg-ink-800">
            Create
          </button>
        </form>
      </section>

      {projects.length === 0 ? (
        <EmptyState
          title="No projects yet"
          description="Create a project, register its first version, then connect the SDK to record and evaluate real application runs."
        />
      ) : (
        <div className="data-surface divide-y divide-slate-100 px-5 sm:px-7">
          {projects.map((project) => (
            <Link
              key={project.id}
              href={`/projects/${project.id}`}
              className="grid gap-3 py-5 transition-colors hover:bg-cyan-50/30 sm:grid-cols-[1fr_auto] sm:items-center"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="font-semibold text-ink-950">{project.name}</h2>
                  <p className="mt-1 text-xs text-slate-500">{project.slug}</p>
                </div>
              </div>
              <p className="mt-2 text-sm text-slate-600">
                {project.description ?? "No description"}
              </p>
              <div className="text-xs text-slate-500 sm:text-right">Created {formatDateTime(project.created_at)}<div className="mt-1 font-medium text-cyan-800">Open project →</div></div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
