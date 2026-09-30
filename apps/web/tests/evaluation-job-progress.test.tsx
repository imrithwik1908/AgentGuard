import { act, render, screen } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { EvaluationJobProgress } from "@/components/evaluation-job-progress";
import type { EvaluationJob } from "@/lib/types";

const refresh = vi.fn();
const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh, replace })
}));

function job(status: EvaluationJob["status"], completed = 0): EvaluationJob {
  return {
    id: "job-1",
    request_id: "request-1",
    queue_job_id: null,
    project_id: "project-1",
    dataset_id: "dataset-1",
    application_version_id: "version-1",
    evaluator_name: "builtin.keyword_coverage",
    status,
    total_cases: 4,
    completed_cases: completed,
    failed_cases: 0,
    max_attempts: 3,
    error: null,
    created_at: "2026-09-30T00:00:00Z",
    started_at: null,
    finished_at: status === "COMPLETED" ? "2026-09-30T00:00:01Z" : null,
    cases: []
  };
}

describe("EvaluationJobProgress", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    refresh.mockReset();
    replace.mockReset();
  });

  afterEach(() => vi.useRealTimers());

  it("keeps polling until the job reaches a terminal state", () => {
    render(<EvaluationJobProgress jobs={[job("RUNNING", 1)]} releaseUrl="/releases" />);

    act(() => vi.advanceTimersByTime(4_500));
    expect(refresh).toHaveBeenCalledTimes(3);
    expect(replace).not.toHaveBeenCalled();
  });

  it("shows completion and opens the release result", () => {
    render(<EvaluationJobProgress jobs={[job("COMPLETED", 3)]} releaseUrl="/releases?pair=1" />);

    expect(screen.getByText("100%")).toBeInTheDocument();
    expect(screen.getByText("Evidence is ready")).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(700));
    expect(replace).toHaveBeenCalledWith("/releases?pair=1");
  });
});
