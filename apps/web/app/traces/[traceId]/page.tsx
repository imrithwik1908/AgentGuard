import Link from "next/link";

import { ApiUnavailable } from "@/components/api-unavailable";
import { EvaluationStatusBadge } from "@/components/evaluation-status-badge";
import { TraceExplorer } from "@/components/trace-explorer";
import { formatDateTime, formatScore } from "@/lib/format";
import { getProject, getTrace, listEvaluations, listVersions } from "@/lib/api";
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

  return (
    <div className="space-y-5">
      <div className="text-sm text-slate-500">
        <Link href="/traces" className="hover:underline">
          Runs
        </Link>{" "}
        / {trace.name}
      </div>
      <section className="overflow-hidden rounded-[2rem] border border-slate-200 bg-white shadow-panel">
        <div className="h-1 bg-gradient-to-r from-cyan-500 via-emerald-500 to-slate-900" />
        <div className="p-5">
        <div className="text-xs font-medium uppercase tracking-wide text-cyan-700">Run investigation</div>
        <h1 className="mt-2 text-2xl font-semibold text-ink-950">{trace.name}</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
          A run is one complete execution of the AI application. Start with what failed and which
          checks recorded evidence, then open execution details only when you need internals.
        </p>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <div className="rounded-2xl bg-slate-50 p-4">
            <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Execution</div>
            <div className="mt-2 text-sm font-semibold text-ink-950">
              {trace.status === "OK" ? "✓ Completed successfully" : trace.status}
            </div>
            <div className="mt-1 text-xs leading-5 text-slate-500">
              Whether the application run crashed or completed.
            </div>
          </div>
          <div className="rounded-2xl bg-slate-50 p-4">
            <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Behavior</div>
            <div className="mt-2 text-sm font-semibold text-ink-950">
              {failedChecks.length > 0
                ? `✕ Failed ${failedChecks.length} evaluation${failedChecks.length === 1 ? "" : "s"}`
                : "No failed check recorded"}
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
        </div>
      </section>

      <section className="rounded-[2rem] border border-slate-200 bg-white p-5 shadow-panel">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-cyan-700">Checks</div>
            <h2 className="mt-2 text-lg font-semibold text-ink-950">Checks for this run</h2>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">
              A check is a stored piece of evidence. It can measure answer behavior, retrieval,
              agent actions, or operational reliability. Internal evaluator IDs stay tucked away.
            </p>
          </div>
          <form action={createHealthEvaluationForTrace}>
            <button className="rounded-full bg-ink-900 px-4 py-2 text-sm font-medium text-white hover:bg-ink-800">
              Run operational checks
            </button>
          </form>
        </div>
        {evaluationError ? (
          <div className="mt-3 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
            {evaluationError}
          </div>
        ) : null}
        {evaluations.items.length > 0 ? (
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {evaluations.items.map((evaluation) => (
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
                      {checkMeaning(evaluation.evaluator_name, evaluation.passed)}
                    </p>
                    <div className="mt-1 text-xs text-slate-500">{formatDateTime(evaluation.created_at)}</div>
                    <details className="mt-1 text-xs text-slate-500">
                      <summary className="cursor-pointer">Advanced evaluator details</summary>
                      <div className="mt-1 font-mono">{evaluation.evaluator_name}</div>
                    </details>
                  </div>
                  <EvaluationStatusBadge status={evaluation.status} />
                </div>
                <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
                  <div className="rounded-xl bg-white/70 p-3">
                    <div className="text-xs uppercase tracking-wide text-slate-500">Score</div>
                    <div className="mt-1 text-ink-950">{formatScore(evaluation.score)}</div>
                  </div>
                  <div className="rounded-xl bg-white/70 p-3">
                    <div className="text-xs uppercase tracking-wide text-slate-500">Threshold</div>
                    <div className="mt-1 text-ink-950">{formatScore(evaluation.threshold)}</div>
                  </div>
                </div>
                {evaluation.explanation ? (
                  <p className="mt-3 text-sm text-slate-600">{evaluation.explanation}</p>
                ) : null}
              </div>
            ))}
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
