import Link from "next/link";

import { ApiUnavailable } from "@/components/api-unavailable";
import { EmptyState } from "@/components/empty-state";
import { MetricCard } from "@/components/metric-card";
import { listDatasets, listProjects, listVersions } from "@/lib/api";
import type { ApplicationVersion, Dataset, Project } from "@/lib/types";

import { createDemoDatasetAction, runDatasetCaseAction } from "./actions";

function projectName(projects: Project[], projectId: string): string {
  return projects.find((project) => project.id === projectId)?.name ?? projectId;
}

function versionsForProject(versions: ApplicationVersion[], projectId: string) {
  return versions.filter((version) => version.project_id === projectId);
}

function caseQuestion(datasetCase: Dataset["cases"][number]): string {
  const question = datasetCase.input.question;
  return typeof question === "string" ? question : JSON.stringify(datasetCase.input);
}

export default async function DatasetsPage({
  searchParams
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const query = await searchParams;
  const datasetError = typeof query.dataset_error === "string" ? query.dataset_error : "";

  let projects;
  let versions;
  let datasets;
  try {
    projects = await listProjects();
    versions = (await Promise.all(projects.map((project) => listVersions(project.id)))).flat();
    datasets = await listDatasets({ limit: 100 });
  } catch (error) {
    return (
      <ApiUnavailable
        title="Test suites cannot reach the AgentGuard API"
        detail={error instanceof Error ? error.message : String(error)}
      />
    );
  }

  const caseCount = datasets.items.reduce((total, dataset) => total + dataset.cases.length, 0);

  return (
    <div className="space-y-8">
      <section className="surface rounded-[2rem] p-6">
        <div className="text-xs font-medium uppercase tracking-[0.22em] text-cyan-700">
          Test
        </div>
        <div className="mt-3 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-3xl font-semibold text-ink-950">Test Suites</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
              A test suite is a set of representative cases used to check whether your AI
              application still behaves correctly after a prompt, model, retrieval, or workflow
              change.
            </p>
          </div>
          <div className="rounded-2xl bg-ink-950 px-4 py-3 text-sm text-white">
            Each case run becomes evidence: run + checks + score.
          </div>
        </div>
      </section>

      <section className="flex flex-col gap-3 rounded-[1.5rem] border border-slate-200/80 bg-white/70 p-3 shadow-panel backdrop-blur md:flex-row">
        <MetricCard label="Suites" value={datasets.total} detail="Behavioral test sets" tone="focus" />
        <MetricCard label="Cases" value={caseCount} detail="Expected behaviors" />
        <MetricCard label="Versions" value={versions.length} detail="Runnable builds" />
      </section>

      {datasetError ? (
        <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          {decodeURIComponent(datasetError)}
        </div>
      ) : null}

      <section className="surface rounded-[2rem] p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-ink-950">Create a demo regression suite</h2>
            <p className="mt-1 text-sm text-slate-600">
              Use this to populate AgentGuard with deterministic behavior checks for the demo agent.
            </p>
          </div>
          {projects.length > 0 ? (
            <form action={createDemoDatasetAction} className="flex flex-wrap gap-2">
              <select
                name="project_id"
                className="rounded-full border border-slate-300 px-3 py-2 text-sm text-ink-950"
                defaultValue={projects[0]?.id}
              >
                {projects.map((project) => (
                  <option key={project.id} value={project.id}>
                    {project.name} ({project.slug})
                  </option>
                ))}
              </select>
              <button className="rounded-full bg-ink-900 px-4 py-2 text-sm font-medium text-white">
                Create suite
              </button>
            </form>
          ) : (
            <Link
              className="rounded-full bg-ink-900 px-4 py-2 text-sm font-medium text-white"
              href="/projects"
            >
              Create project first
            </Link>
          )}
        </div>
      </section>

      {datasets.items.length > 0 ? (
        <section className="space-y-5">
          {datasets.items.map((dataset) => {
            const runnableVersions = versionsForProject(versions, dataset.project_id);
            return (
              <div key={dataset.id} className="overflow-hidden rounded-[2rem] border border-slate-200 bg-white/88 shadow-panel">
                <div className="border-b border-slate-200 bg-slate-50/70 p-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
                        {projectName(projects, dataset.project_id)}
                      </div>
                      <h2 className="mt-1 text-lg font-semibold text-ink-950">{dataset.name}</h2>
                      <p className="mt-1 max-w-3xl text-sm text-slate-600">
                        {dataset.description ?? "No description"}
                      </p>
                    </div>
                    <div className="rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-700 shadow-sm">
                      {dataset.cases.length} cases
                    </div>
                  </div>
                </div>
                <div className="divide-y divide-slate-100">
                  {dataset.cases.map((datasetCase) => (
                    <div key={datasetCase.id} className="flex flex-col gap-3 p-5 lg:flex-row lg:items-center lg:justify-between">
                      <div className="flex gap-4">
                        <div className="mt-1 h-10 w-1.5 shrink-0 rounded-full bg-gradient-to-b from-cyan-500 to-emerald-500" />
                        <div>
                          <div className="font-medium text-ink-950">{datasetCase.name}</div>
                          <div className="mt-1 text-sm text-slate-600">{caseQuestion(datasetCase)}</div>
                          <div className="mt-2 inline-flex rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">
                            Expected: {datasetCase.expected_substring ?? "none"}
                          </div>
                        </div>
                      </div>
                      <form action={runDatasetCaseAction} className="flex flex-wrap items-end gap-2">
                        <input type="hidden" name="case_id" value={datasetCase.id} />
                        <select
                          name="application_version_id"
                          className="rounded-full border border-slate-300 px-3 py-2 text-sm text-ink-950"
                          disabled={runnableVersions.length === 0}
                        >
                          {runnableVersions.map((version) => (
                            <option key={version.id} value={version.id}>
                              {version.version}
                            </option>
                          ))}
                        </select>
                        <button
                          className="rounded-full bg-ink-900 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-slate-300"
                          disabled={runnableVersions.length === 0}
                        >
                          Run case
                        </button>
                      </form>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </section>
      ) : (
        <EmptyState
          title="No test suites yet"
          description="Create a demo test suite to start measuring whether an agent version still satisfies expected behaviors."
        />
      )}
    </div>
  );
}
