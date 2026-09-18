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
    const timer = window.setTimeout(
      () => (finished ? router.replace(releaseUrl) : router.refresh()),
      finished ? 700 : 1500
    );
    return () => window.clearTimeout(timer);
  }, [finished, releaseUrl, router]);

  const completedCases = jobs.reduce((total, job) => total + job.completed_cases, 0);
  const failedCases = jobs.reduce((total, job) => total + job.failed_cases, 0);
  const totalCases = jobs.reduce((total, job) => total + job.total_cases, 0);
  const percent = totalCases ? Math.round(((completedCases + failedCases) / totalCases) * 100) : 0;

  return (
    <section className="overflow-hidden rounded-2xl border border-cyan-200 bg-white shadow-panel">
      <div className="h-1 bg-cyan-500 transition-[width]" style={{ width: `${Math.max(percent, 3)}%` }} />
      <div className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-700">Evaluation in progress</div>
            <h2 className="mt-2 text-xl font-semibold text-ink-950">
              {finished ? "Evidence is ready" : "AgentGuard is checking both versions"}
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              {finished
                ? "Opening the paired comparison and release decision."
                : "Workers are evaluating each test case. You can leave this page; progress is stored."}
            </p>
          </div>
          <div className="text-right">
            <div className="text-2xl font-semibold text-ink-950">{percent}%</div>
            <div className="text-xs text-slate-500">{completedCases} completed · {failedCases} errors</div>
          </div>
        </div>
        <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {jobs.map((job) => (
            <div key={job.id} className="rounded-xl bg-slate-50 px-3 py-2 text-sm">
              <div className="truncate font-medium text-slate-800">{job.evaluator_name.replace("builtin.", "")}</div>
              <div className="mt-1 flex items-center justify-between text-xs text-slate-500">
                <span>{job.completed_cases}/{job.total_cases} cases</span>
                <span>{job.status}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
