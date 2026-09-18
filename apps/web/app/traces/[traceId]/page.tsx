import Link from "next/link";

import { ApiUnavailable } from "@/components/api-unavailable";
import { EvaluationStatusBadge } from "@/components/evaluation-status-badge";
import { TraceExplorer } from "@/components/trace-explorer";
import { formatDateTime, formatScore } from "@/lib/format";
import { ApiRequestError, getProject, getTrace, listEvaluations, listVersions } from "@/lib/api";
import {
  explainEvaluation,
  evaluationReliability,
  retrievalIds,
  toolNames,
  traceAnswer
} from "@/lib/evaluation-explanations";
import { evaluatorInfo } from "@/lib/product-intelligence";

import { createStatusEvaluationAction } from "../actions";

function checkMeaning(evaluationName: string, passed: boolean): string {
  const info = evaluatorInfo(evaluationName);
  if (info.category === "Answer Quality") {
    return passed
      ? "The answer matched the expected behavior for this case."
      : "The answer did not meet the expected behavior for this case.";
  }
  if (info.category === "Retrieval") {
    return passed
      ? "The retrieval evidence looks acceptable for this run."
      : "The retrieval evidence suggests the app may have fetched weak or wrong context.";
  }
  if (info.category === "Agent Behavior") {
    return passed
      ? "The agent behavior matched the expected action pattern."
      : "The agent may have selected the wrong action, tool, or workflow path.";
  }
  return passed
    ? "The run produced usable operational evidence."
    : "The run has an operational issue that can affect reliability or debugging.";
}

export default async function TraceDetailPage({
  params,
  searchParams
}: {
  params: Promise<{ traceId: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { traceId } = await params;
  const query = await searchParams;
  const evaluationError = typeof query.evaluation_error === "string" ? query.evaluation_error : "";
  const comparisonRole = query.role === "baseline" || query.role === "candidate" ? query.role : null;
  const baselineVersionId = typeof query.baseline_version_id === "string" ? query.baseline_version_id : "";
  const candidateVersionId = typeof query.candidate_version_id === "string" ? query.candidate_version_id : "";
  let trace;
  let project;
  let versions;
  let evaluations;
  try {
    trace = await getTrace(traceId);
    project = await getProject(trace.project_id);
    [versions, evaluations] = await Promise.all([
      listVersions(project.id),
      listEvaluations({ traceId: trace.id })
    ]);
  } catch (error) {
    if (error instanceof ApiRequestError && error.status === 404) {
      return (
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-panel">
          <div className="text-xs font-medium uppercase tracking-[0.18em] text-slate-500">
            Run unavailable
          </div>
          <h1 className="mt-2 text-xl font-semibold text-ink-950">
            This run was not found in your workspace.
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            It may have been removed, or the link may belong to a different workspace. AgentGuard
            does not reveal resources outside your workspace.
          </p>
          <Link
            href="/traces"
            className="mt-5 inline-flex rounded-full bg-ink-950 px-4 py-2 text-sm font-medium text-white hover:bg-ink-800"
          >
            Back to runs
          </Link>
        </section>
      );
    }
    return (
      <ApiUnavailable
        title="Run investigation cannot reach the AgentGuard API"
        detail={error instanceof Error ? error.message : String(error)}
      />
    );
  }
  const version = versions.find((candidate) => candidate.id === trace.application_version_id) ?? null;
  const createHealthEvaluationForTrace = createStatusEvaluationAction.bind(null, trace.id);
  const failedChecks = evaluations.items.filter((evaluation) => !evaluation.passed);
  const likelyFailureArea = failedChecks[0]
    ? evaluatorInfo(failedChecks[0].evaluator_name).category
    : trace.status === "ERROR"
      ? "Operational"
      : null;
  const answer = traceAnswer(trace);
  const sources = retrievalIds(trace);
  const tools = toolNames(trace);
  const releaseHref = baselineVersionId && candidateVersionId
    ? `/releases?baseline_version_id=${baselineVersionId}&candidate_version_id=${candidateVersionId}`
    : "/releases";

  return (
    <div className="space-y-5">
      <div className="text-sm text-slate-500">
        <Link href={comparisonRole ? releaseHref : "/traces"} className="hover:underline">
          {comparisonRole ? "Release comparison" : "Runs"}
        </Link>{" "}
        / {trace.name}
      </div>
      <section className="overflow-hidden rounded-[2rem] border border-slate-200 bg-white shadow-panel">
        <div className="h-1 bg-gradient-to-r from-cyan-500 via-emerald-500 to-slate-900" />
        <div className="p-5">
        <div className="flex flex-wrap items-center gap-2 text-xs font-medium uppercase tracking-wide text-cyan-700">
          <span>Run investigation</span>
          {comparisonRole ? (
            <span className={comparisonRole === "candidate" ? "rounded-full bg-amber-100 px-2 py-1 text-amber-800" : "rounded-full bg-cyan-100 px-2 py-1 text-cyan-800"}>
              {comparisonRole} run
            </span>
          ) : null}
        </div>
        <h1 className="mt-2 text-2xl font-semibold text-ink-950">{trace.name}</h1>
        <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-sm text-slate-600">
          <span><strong className="text-ink-950">Project:</strong> {project.name}</span>
          <span><strong className="text-ink-950">Version:</strong> {version?.version ?? trace.application_version_id}</span>
          <span><strong className="text-ink-950">Started:</strong> {formatDateTime(trace.started_at)}</span>
        </div>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
          {comparisonRole
            ? `This is the ${comparisonRole} execution in the selected release comparison. Baseline and candidate are roles in that comparison; the stored run belongs to version ${version?.version ?? trace.application_version_id}.`
            : "A run belongs to an application version. It becomes a baseline or candidate only when you select it in a release comparison."}
        </p>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <div className="rounded-2xl bg-slate-50 p-4">
            <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Execution</div>
            <div className="mt-2 text-sm font-semibold text-ink-950">
              {trace.status === "OK" ? "Completed successfully" : trace.status}
            </div>
            <div className="mt-1 text-xs leading-5 text-slate-500">
              Whether the application run crashed or completed.
            </div>
          </div>
          <div className="rounded-2xl bg-slate-50 p-4">
            <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Behavior</div>
            <div className="mt-2 text-sm font-semibold text-ink-950">
              {failedChecks.length > 0
                ? `Failed ${failedChecks.length} evaluation${failedChecks.length === 1 ? "" : "s"}`
                : evaluations.items.length > 0 ? "All recorded checks passed" : "Not evaluated yet"}
            </div>
            <div className="mt-1 text-xs leading-5 text-slate-500">
              Whether the completed output satisfied stored checks.
            </div>
          </div>
          <div className="rounded-2xl bg-slate-50 p-4">
            <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Likely area</div>
            <div className="mt-2 text-sm font-semibold text-ink-950">
              {likelyFailureArea ?? "No failure evidence yet"}
            </div>
            <div className="mt-1 text-xs leading-5 text-slate-500">
              Category, not a causal claim.
            </div>
          </div>
        </div>
        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Application answer</div>
            <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700">
              {answer ?? "No generated answer was recorded for this run."}
            </p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Evidence used</div>
            <dl className="mt-2 space-y-3 text-sm">
              <div><dt className="font-medium text-ink-950">Retrieved sources</dt><dd className="mt-1 text-slate-600">{sources.length ? sources.join(", ") : "None recorded"}</dd></div>
              <div><dt className="font-medium text-ink-950">Tools called</dt><dd className="mt-1 text-slate-600">{tools.length ? tools.join(", ") : "None recorded"}</dd></div>
            </dl>
          </div>
        </div>
        </div>
      </section>

      <section className="rounded-[2rem] border border-slate-200 bg-white p-5 shadow-panel">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-cyan-700">Checks</div>
            <h2 className="mt-2 text-lg font-semibold text-ink-950">Evaluation evidence for this run</h2>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">
              A check is a stored piece of evidence. It can measure answer behavior, retrieval,
              agent actions, or operational reliability. Internal evaluator IDs stay tucked away.
            </p>
          </div>
          <div className="max-w-sm text-right">
            <form action={createHealthEvaluationForTrace}>
              <button className="rounded-full bg-ink-900 px-4 py-2 text-sm font-medium text-white hover:bg-ink-800">
                Check execution health
              </button>
            </form>
            <p className="mt-2 text-xs leading-5 text-slate-500">
              Checks completion, step errors, a 2-second latency budget, and whether enough debug evidence was recorded. It does not judge answer correctness.
            </p>
          </div>
        </div>
        {evaluationError ? (
          <div className="mt-3 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
            {evaluationError}
          </div>
        ) : null}
        {evaluations.items.length > 0 ? (
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {evaluations.items.map((evaluation) => {
              const reasoning = explainEvaluation(evaluation);
              return (
              <div
                key={evaluation.id}
                className={`rounded-2xl border p-4 ${
                  evaluation.passed
                    ? "border-emerald-200 bg-emerald-50/70"
                    : "border-red-200 bg-red-50/70"
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                      {evaluatorInfo(evaluation.evaluator_name).category}
                    </div>
                    <div className="font-medium text-ink-950">
                      {evaluation.label ?? evaluatorInfo(evaluation.evaluator_name).name}
                    </div>
                    <p className="mt-1 text-sm leading-6 text-slate-700">
                      {reasoning.summary || checkMeaning(evaluation.evaluator_name, evaluation.passed)}
                    </p>
                    <div className="mt-3 rounded-xl bg-white/75 p-3 text-xs leading-5 text-slate-700">
                      <div className="font-semibold text-ink-950">How this score was calculated</div>
                      <div className="mt-1">{reasoning.calculation}</div>
                      {reasoning.missing.length ? (
                        <div className="mt-1 text-red-700">Missing: {reasoning.missing.join(", ")}</div>
                      ) : null}
                      <div className="mt-2 border-t border-slate-200 pt-2 text-slate-500">
                        {evaluationReliability(evaluation)}
                      </div>
                    </div>
                    <div className="mt-1 text-xs text-slate-500">{formatDateTime(evaluation.created_at)}</div>
                    <details className="mt-1 text-xs text-slate-500">
                      <summary className="cursor-pointer">Advanced evaluator details</summary>
                      <dl className="mt-2 grid gap-2 rounded-xl bg-white/70 p-3 font-mono">
                        <div>raw score: {formatScore(evaluation.score)}</div>
                        <div>threshold: {formatScore(evaluation.threshold)}</div>
                        <div>evaluator: {evaluation.evaluator_name}</div>
                        <div>version: {evaluation.evaluator_version}</div>
                        <div>method: {evaluation.method}</div>
                        {evaluation.judge_model ? <div>judge model: {evaluation.judge_model}</div> : null}
                      </dl>
                    </details>
                  </div>
                  <EvaluationStatusBadge status={evaluation.status} />
                </div>
                {evaluation.explanation ? (
                  <p className="mt-3 text-sm text-slate-600">{evaluation.explanation}</p>
                ) : null}
              </div>
              );
            })}
          </div>
        ) : (
          <p className="mt-4 text-sm text-slate-600">
            No checks have been recorded for this run yet.
          </p>
        )}
      </section>

      <details className="rounded-[2rem] border border-slate-200 bg-white p-4 shadow-panel">
        <summary className="cursor-pointer text-sm font-semibold text-ink-950">
          View execution details
        </summary>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
          The trace is the recorded sequence of important steps inside this run. A step is one
          recorded operation, such as retrieval, a model call, or a tool call.
          Step color shows execution health; behavioral checks are shown above.
        </p>
        <div className="mt-5">
          <TraceExplorer trace={trace} project={project} version={version} />
        </div>
      </details>
    </div>
  );
}
