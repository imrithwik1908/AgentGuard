import Link from "next/link";

import { ApiUnavailable } from "@/components/api-unavailable";
import { EmptyState } from "@/components/empty-state";
import { getEvaluationCapabilities, listDatasets, listProjects, listVersions } from "@/lib/api";
import type { ApplicationVersion, Dataset, Project } from "@/lib/types";

import {
  createDemoDatasetAction,
  evaluateCandidateAction,
  runDatasetCaseAction,
  runDatasetSuiteAction
} from "./actions";

function projectName(projects: Project[], projectId: string): string {
  return projects.find((project) => project.id === projectId)?.name ?? projectId;
}

function versionsForProject(versions: ApplicationVersion[], projectId: string) {
  return versions
    .filter((version) => version.project_id === projectId)
    .sort((left, right) => Date.parse(left.created_at) - Date.parse(right.created_at));
}

function caseQuestion(datasetCase: Dataset["cases"][number]): string {
  const question = datasetCase.input.question;
  return typeof question === "string" ? question : JSON.stringify(datasetCase.input);
}

function expectedBehavior(datasetCase: Dataset["cases"][number]): string {
  if (datasetCase.expected_substring) return datasetCase.expected_substring;
  if (datasetCase.expected_output) return JSON.stringify(datasetCase.expected_output);
  return "No explicit expected behavior stored yet";
}

function caseChecks(datasetCase: Dataset["cases"][number]): string[] {
  const checks = [];
  if (datasetCase.expected_substring || datasetCase.expected_output) checks.push("Answer requirement");
  if (datasetCase.metadata?.required_sources || datasetCase.metadata?.expected_document_ids) {
    checks.push("Required source");
  }
  if (datasetCase.metadata?.expected_tool || datasetCase.metadata?.expected_tools) {
    checks.push("Expected tool");
  }
  if (datasetCase.metadata?.forbidden_tools) checks.push("Forbidden tool");
  if (datasetCase.metadata?.latency_budget_ms) checks.push("Latency budget");
  return checks.length > 0 ? checks : ["Runtime success"];
}

function caseName(value: string): string {
  return value
    .split("-")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
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
  let capabilities;
  try {
    [projects, capabilities] = await Promise.all([listProjects(), getEvaluationCapabilities()]);
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

  return (
    <div className="space-y-7">
      <section className="border-b border-slate-200 pb-6 pt-2">
        <div className="text-xs font-semibold uppercase tracking-wide text-cyan-700">Test</div>
        <h1 className="mt-2 text-3xl font-semibold text-ink-950">Test Suites</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
          A test suite is a reusable set of scenarios your application should handle correctly.
          Run the same suite against two versions to see what changed.
        </p>
      </section>

      {datasetError ? (
        <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          {decodeURIComponent(datasetError)}
        </div>
      ) : null}

      <details className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm shadow-sm">
        <summary className="cursor-pointer font-medium text-slate-700">Create an example suite</summary>
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4">
          <p className="text-sm text-slate-600">Add three starter scenarios to an existing project.</p>
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
      </details>

      {datasets.items.length > 0 ? (
        <section className="space-y-5">
          {datasets.items.map((dataset) => {
            const runnableVersions = versionsForProject(versions, dataset.project_id);
            return (
              <div key={dataset.id} className="border-y border-slate-200 bg-white">
                <div className="border-b border-slate-200 py-5">
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
                    <div className="text-sm text-slate-500">
                      {dataset.cases.length} cases
                    </div>
                  </div>
                  {runnableVersions.length > 0 ? (
                    <div className="mt-5">
                      <form
                        action={evaluateCandidateAction}
                        className="flex flex-col gap-4 border-l-2 border-cyan-500 bg-cyan-50/40 px-4 py-3 xl:flex-row xl:items-end"
                      >
                        <input type="hidden" name="dataset_id" value={dataset.id} />
                        <div className="min-w-52 flex-1">
                          <div className="text-sm font-semibold text-ink-950">Compare two versions</div>
                          <p className="mt-1 text-xs text-slate-600">
                            {capabilities.ai_judges_enabled
                              ? `Semantic judging is on · ${capabilities.judge_model}`
                              : "Deterministic checks only · semantic judging is not connected"}
                          </p>
                        </div>
                        <div className="flex flex-wrap items-end gap-2">
                          <label className="flex items-center gap-2 text-xs text-slate-600">
                            Baseline
                            <select
                              name="baseline_version_id"
                              className="rounded-full border border-cyan-200 bg-white px-3 py-2 text-sm text-ink-950"
                              defaultValue={runnableVersions[0]?.id}
                            >
                              {runnableVersions.map((version) => (
                                <option key={version.id} value={version.id}>
                                  {version.version}
                                </option>
                              ))}
                            </select>
                          </label>
                          <label className="flex items-center gap-2 text-xs text-slate-600">
                            Candidate
                            <select
                              name="candidate_version_id"
                              className="rounded-full border border-cyan-200 bg-white px-3 py-2 text-sm text-ink-950"
                              defaultValue={runnableVersions[1]?.id ?? runnableVersions[0]?.id}
                            >
                              {runnableVersions.map((version) => (
                                <option key={version.id} value={version.id}>
                                  {version.version}
                                </option>
                              ))}
                            </select>
                          </label>
                          <button
                            className="rounded-full bg-cyan-600 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
                            disabled={runnableVersions.length < 2}
                          >
                            Evaluate candidate
                          </button>
                        </div>
                      </form>
                      <details className="mt-3 text-xs text-slate-500">
                        <summary className="cursor-pointer font-medium">Built-in test runner</summary>
                        <form action={runDatasetSuiteAction} className="mt-3 flex flex-wrap items-center gap-2 rounded-lg bg-slate-50 p-3">
                          {dataset.cases.map((datasetCase) => (
                            <input key={datasetCase.id} type="hidden" name="case_id" value={datasetCase.id} />
                          ))}
                          <span>Generate simple stored runs for</span>
                          <select name="application_version_id" className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-ink-950">
                            {runnableVersions.map((version) => <option key={version.id} value={version.id}>{version.version}</option>)}
                          </select>
                          <button className="rounded-lg bg-slate-800 px-3 py-2 text-sm font-medium text-white">Run suite</button>
                        </form>
                      </details>
                    </div>
                  ) : null}
                </div>
                <div className="divide-y divide-slate-100">
                  {dataset.cases.map((datasetCase) => (
                    <details key={datasetCase.id} className="group py-4">
                      <summary className="flex cursor-pointer list-none items-center justify-between gap-4">
                        <div className="min-w-0">
                          <div className="font-medium text-ink-950">{caseName(datasetCase.name)}</div>
                          <div className="mt-1 line-clamp-1 text-sm text-slate-600">{caseQuestion(datasetCase)}</div>
                        </div>
                        <div className="flex shrink-0 items-center gap-3">
                          <span className="hidden text-xs text-slate-500 sm:block">{caseChecks(datasetCase).length} checks</span>
                          <span className="text-slate-400 transition group-open:rotate-90">›</span>
                        </div>
                      </summary>
                      <div className="mt-4 space-y-4 border-t border-slate-100 pt-4 text-sm">
                            <div>
                              <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Question</div>
                              <div className="mt-1 text-slate-700">{caseQuestion(datasetCase)}</div>
                            </div>
                            <div>
                              <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Expected</div>
                              <div className="mt-1 text-slate-700">{expectedBehavior(datasetCase)}</div>
                            </div>
                            <div className="flex flex-wrap items-center gap-2">
                              <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Checks</div>
                              <div className="flex flex-wrap gap-1">
                                {caseChecks(datasetCase).map((check) => (
                                  <span key={check} className="border-l border-slate-300 px-2 text-xs text-slate-600 first:border-0 first:pl-0">
                                    {check}
                                  </span>
                                ))}
                              </div>
                            </div>
                      </div>
                      <form action={runDatasetCaseAction} className="mt-4 flex flex-wrap items-center justify-end gap-2">
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
                          Run this case
                        </button>
                      </form>
                    </details>
                  ))}
                </div>
              </div>
            );
          })}
        </section>
      ) : (
        <EmptyState
          title="No test suites yet"
          description="Create a starter suite to begin checking whether a version still satisfies expected behaviors."
        />
      )}
    </div>
  );
}
