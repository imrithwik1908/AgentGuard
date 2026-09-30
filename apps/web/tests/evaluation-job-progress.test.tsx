import { act, render, screen } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { EvaluationJobProgress } from "@/components/evaluation-job-progress";
import type { EvaluationJob } from "@/lib/types";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace })
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
    replace.mockReset();
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(new Promise<Response>(() => undefined)));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("requests fresh status while the job is still running", () => {
    render(<EvaluationJobProgress jobs={[job("RUNNING", 1)]} releaseUrl="/releases" />);

    expect(fetch).toHaveBeenCalledOnce();
    expect(replace).not.toHaveBeenCalled();
  });

  it("updates from fresh job status and opens the release result", async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => [job("COMPLETED", 4)]
    } as Response);

    render(<EvaluationJobProgress jobs={[job("RUNNING", 1)]} releaseUrl="/releases?pair=1" />);

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(screen.getByText("100%")).toBeInTheDocument();
    expect(screen.getByText("Evidence is ready")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open comparison" })).toHaveAttribute(
      "href",
      "/releases?pair=1"
    );
    await act(async () => vi.advanceTimersByTimeAsync(700));
    expect(replace).toHaveBeenCalledWith("/releases?pair=1");
  });

  it("shows completion and opens the release result", () => {
    render(<EvaluationJobProgress jobs={[job("COMPLETED", 3)]} releaseUrl="/releases?pair=1" />);

    expect(screen.getByText("100%")).toBeInTheDocument();
    expect(screen.getByText("Evidence is ready")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open comparison" })).toHaveAttribute(
      "href",
      "/releases?pair=1"
    );
    act(() => vi.advanceTimersByTime(700));
    expect(replace).toHaveBeenCalledWith("/releases?pair=1");
  });
});
