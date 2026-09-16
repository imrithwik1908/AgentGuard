import { describe, expect, it } from "vitest";

import {
  classifyEvaluationPairs,
  deriveReleaseState,
  evaluatorInfo,
  findDefaultComparisonPair,
  summarizeConfigChanges
} from "@/lib/product-intelligence";
import type { ApplicationVersion, EvaluationResult, Project, Trace } from "@/lib/types";

const project: Project = {
  id: "project-1",
  workspace_id: null,
  name: "Research Agent",
  slug: "research-agent",
  description: null,
  created_at: "2026-09-12T00:00:00.000Z",
  updated_at: "2026-09-12T00:00:00.000Z"
};

function version(id: string, createdAt: string, model = "demo-model"): ApplicationVersion {
  return {
    id,
    project_id: project.id,
    name: id,
    version: id,
    git_commit: null,
    model_config: { model },
    prompt_config: {},
    retrieval_config: {},
    agent_config: {},
    metadata: {},
    created_at: createdAt
  };
}

function evaluation(input: Partial<EvaluationResult> & { id: string }): EvaluationResult {
  return {
    project_id: project.id,
    dataset_id: "dataset-1",
    dataset_case_id: "case-1",
    application_version_id: "v1",
    trace_id: "trace-1",
    evaluator_name: "builtin.answer_contains",
    score: "1.0000",
    threshold: "1.0000",
    status: "PASS",
    passed: true,
    label: "Expected answer substring found",
    explanation: null,
    metadata: {},
    created_at: "2026-09-12T00:00:00.000Z",
    ...input
  };
}

const trace: Trace = {
  id: "trace-2",
  project_id: project.id,
  application_version_id: "v2",
  external_trace_id: null,
  name: "dataset:refund-policy",
  status: "ERROR",
  input: null,
  output: null,
  metadata: {},
  started_at: "2026-09-12T00:00:00.000Z",
  ended_at: "2026-09-12T00:00:01.000Z",
  duration_ms: 1000,
  total_input_tokens: null,
  total_output_tokens: null,
  estimated_cost: null,
  error: null,
  created_at: "2026-09-12T00:00:01.000Z",
  spans: []
};

describe("product intelligence helpers", () => {
  it("maps internal evaluator names to user-facing categories", () => {
    expect(evaluatorInfo("builtin.answer_contains").category).toBe("Answer Quality");
    expect(evaluatorInfo("builtin.trace_health.latency_budget").name).toBe("Latency budget");
  });

  it("finds a default baseline/candidate pair by version age", () => {
    const pair = findDefaultComparisonPair(
      [project],
      [version("v1", "2026-09-12T00:00:00.000Z"), version("v2", "2026-09-13T00:00:00.000Z")]
    );

    expect(pair?.baseline.id).toBe("v1");
    expect(pair?.candidate.id).toBe("v2");
  });

  it("summarizes stored configuration changes without inventing causality", () => {
    const changes = summarizeConfigChanges(
      version("v1", "2026-09-12T00:00:00.000Z", "gpt-a"),
      version("v2", "2026-09-13T00:00:00.000Z", "gpt-b")
    );

    expect(changes[0].label).toBe("Model configuration");
    expect(changes[0].evidence).toBe("observed");
  });

  it("buckets paired behavioral cases into regressions", () => {
    const buckets = classifyEvaluationPairs({
      evaluations: [
        evaluation({ id: "base", application_version_id: "v1", trace_id: "trace-1" }),
        evaluation({
          id: "base-latency",
          application_version_id: "v1",
          trace_id: "trace-1",
          evaluator_name: "builtin.trace_health.latency_budget",
          score: "1.0000",
          status: "PASS",
          passed: true
        }),
        evaluation({
          id: "candidate",
          application_version_id: "v2",
          trace_id: "trace-2",
          score: "0.0000",
          status: "FAIL",
          passed: false,
          label: "Expected answer substring missing"
        }),
        evaluation({
          id: "candidate-latency",
          application_version_id: "v2",
          trace_id: "trace-2",
          evaluator_name: "builtin.trace_health.latency_budget",
          score: "1.0000",
          status: "PASS",
          passed: true
        })
      ],
      traces: [trace],
      baselineVersionId: "v1",
      candidateVersionId: "v2"
    });

    expect(buckets.regressed).toHaveLength(1);
    expect(buckets.regressed[0].candidateTrace?.id).toBe("trace-2");
    expect(buckets.regressed[0].candidateEvaluations).toHaveLength(2);
  });

  it("does not call missing one-sided evidence a regression", () => {
    const buckets = classifyEvaluationPairs({
      evaluations: [
        evaluation({
          id: "candidate-only",
          application_version_id: "v2",
          trace_id: "trace-2",
          score: "0.0000",
          status: "FAIL",
          passed: false
        })
      ],
      traces: [trace],
      baselineVersionId: "v1",
      candidateVersionId: "v2"
    });

    expect(buckets.regressed).toHaveLength(0);
    expect(buckets.notComparable).toHaveLength(1);
  });

  it("derives insufficient evidence instead of regression when cases are not comparable", () => {
    const state = deriveReleaseState(
      { regressed: [], improved: [], unchanged: [], notComparable: [] },
      {
        project_id: project.id,
        baseline_version_id: "v1",
        candidate_version_id: "v2",
        baseline: {
          project_id: project.id,
          application_version_id: "v1",
          evaluation_count: 1,
          trace_count: 1,
          pass_count: 1,
          fail_count: 0,
          error_count: 0,
          pass_rate: "1.0000",
          average_score: "1.0000"
        },
        candidate: {
          project_id: project.id,
          application_version_id: "v2",
          evaluation_count: 1,
          trace_count: 1,
          pass_count: 0,
          fail_count: 1,
          error_count: 0,
          pass_rate: "0.0000",
          average_score: "0.0000"
        },
        score_delta: "-1.0000",
        pass_rate_delta: "-1.0000",
        regression_count_delta: 1
      }
    );

    expect(state.state).toBe("INSUFFICIENT_EVIDENCE");
  });
});
