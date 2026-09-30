"use client";

import { useEffect, useMemo, useState } from "react";
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
  const [currentJobs, setCurrentJobs] = useState(jobs);
  const [statusError, setStatusError] = useState(false);
  const jobIds = useMemo(() => jobs.map((job) => job.id).join(","), [jobs]);
  const finished = currentJobs.length > 0 && currentJobs.every((job) => TERMINAL.has(job.status));

  useEffect(() => setCurrentJobs(jobs), [jobs]);

  useEffect(() => {
    if (finished) {
      const redirect = window.setTimeout(() => router.replace(releaseUrl), 700);
      return () => window.clearTimeout(redirect);
    }

    let active = true;
    const refreshStatus = async () => {
      try {
        const response = await fetch(`/api/evaluation-jobs?job_ids=${encodeURIComponent(jobIds)}`, {
          cache: "no-store"
        });
        if (!response.ok) throw new Error("Evaluation status request failed");
        const nextJobs = (await response.json()) as EvaluationJob[];
        if (active) {
          setCurrentJobs(nextJobs);
          setStatusError(false);
        }
      } catch {
        if (active) setStatusError(true);
      }
    };

    void refreshStatus();
    const poll = window.setInterval(() => void refreshStatus(), 1500);
    return () => {
      active = false;
      window.clearInterval(poll);
    };
  }, [finished, jobIds, releaseUrl, router]);

  const completedCases = currentJobs.reduce((total, job) => total + job.completed_cases, 0);
  const failedCases = currentJobs.reduce((total, job) => total + job.failed_cases, 0);
  const totalCases = currentJobs.reduce((total, job) => total + job.total_cases, 0);
  const percent = finished
    ? 100
    : totalCases
      ? Math.round(((completedCases + failedCases) / totalCases) * 100)
      : 0;
  const completedJobs = currentJobs.filter((job) => TERMINAL.has(job.status)).length;

  return (
    <section className="border-y border-cyan-200 bg-cyan-50/30">
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
            <div className="text-xs text-slate-500">{completedJobs} of {currentJobs.length} checks finished</div>
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
        {statusError ? (
          <p className="mt-3 text-sm text-amber-800">
            Status update was interrupted. AgentGuard will keep trying automatically.
          </p>
        ) : null}
        {finished ? (
          <a
            href={releaseUrl}
            className="mt-4 inline-flex rounded-full bg-ink-950 px-4 py-2 text-sm font-medium text-white hover:bg-ink-800"
          >
            Open comparison
          </a>
        ) : null}
        <details className="mt-4 border-t border-cyan-100 pt-3 text-xs text-slate-500">
          <summary className="cursor-pointer font-medium">View check progress</summary>
          <div className="mt-3 divide-y divide-slate-200 border-y border-slate-200 bg-white">
            {currentJobs.map((job) => (
              <div key={job.id} className="flex items-center justify-between gap-4 px-3 py-2">
                <div className="truncate font-medium text-slate-700">{job.evaluator_name.replace("builtin.", "").replaceAll("_", " ")}</div>
                <div className="flex shrink-0 items-center gap-4 text-slate-500">
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
