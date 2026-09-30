"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import type { EvaluationJob } from "@/lib/types";

const TERMINAL = new Set(["COMPLETED", "PARTIAL", "FAILED"]);

export function EvaluationJobProgress({
  jobs,
  releaseUrl
}: {
  jobs: EvaluationJob[];
  releaseUrl: string;
}) {
  const router = useRouter();
  const finished = jobs.length > 0 && jobs.every((job) => TERMINAL.has(job.status));

  useEffect(() => {
    if (finished) {
      const redirect = window.setTimeout(() => router.replace(releaseUrl), 700);
      return () => window.clearTimeout(redirect);
    }
    const poll = window.setInterval(() => router.refresh(), 1500);
    return () => window.clearInterval(poll);
  }, [finished, releaseUrl, router]);

  const completedCases = jobs.reduce((total, job) => total + job.completed_cases, 0);
  const failedCases = jobs.reduce((total, job) => total + job.failed_cases, 0);
  const totalCases = jobs.reduce((total, job) => total + job.total_cases, 0);
  const percent = finished
    ? 100
    : totalCases
      ? Math.round(((completedCases + failedCases) / totalCases) * 100)
      : 0;
  const completedJobs = jobs.filter((job) => TERMINAL.has(job.status)).length;

  return (
    <section className="overflow-hidden rounded-xl border border-cyan-200 bg-white shadow-panel">
      <div className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-cyan-700">Evaluation</div>
            <h2 className="mt-2 text-xl font-semibold text-ink-950">
              {finished ? "Evidence is ready" : "AgentGuard is checking both versions"}
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              {finished
                ? "Opening the paired comparison and release decision."
                : "Checking the same cases for both versions. This page updates automatically."}
            </p>
          </div>
          <div className="text-right">
            <div className="text-2xl font-semibold text-ink-950">{percent}%</div>
            <div className="text-xs text-slate-500">{completedJobs} of {jobs.length} checks finished</div>
          </div>
        </div>
        <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100">
          <div className="h-full rounded-full bg-cyan-500 transition-all" style={{ width: `${Math.max(percent, 3)}%` }} />
        </div>
        {failedCases > 0 ? (
          <p className="mt-3 text-sm text-amber-800">
            {failedCases} case{failedCases === 1 ? "" : "s"} could not be checked. Completed evidence will still be preserved.
          </p>
        ) : null}
        <details className="mt-3 text-xs text-slate-500">
          <summary className="cursor-pointer font-medium">View check progress</summary>
          <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {jobs.map((job) => (
              <div key={job.id} className="rounded-lg bg-slate-50 px-3 py-2">
                <div className="truncate font-medium text-slate-700">{job.evaluator_name.replace("builtin.", "")}</div>
                <div className="mt-1 flex items-center justify-between">
                  <span>{job.completed_cases}/{job.total_cases} cases</span>
                  <span>{job.status.toLowerCase()}</span>
                </div>
              </div>
            ))}
          </div>
        </details>
      </div>
    </section>
  );
}
