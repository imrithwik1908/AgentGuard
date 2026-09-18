import { describe, expect, it } from "vitest";

import { explainEvaluation, observedRuntimeChanges, retrievalIds, traceAnswer } from "@/lib/evaluation-explanations";
import type { EvaluationResult, Trace } from "@/lib/types";

function evaluation(overrides: Partial<EvaluationResult> = {}): EvaluationResult {
  return {
    id: "evaluation-1",
    project_id: "project-1",
    dataset_id: "dataset-1",
    dataset_case_id: "case-1",
    application_version_id: "version-1",
    trace_id: "trace-1",
    evaluator_name: "builtin.keyword_coverage",
    evaluator_version: "1.0.0",
    method: "DETERMINISTIC_BEHAVIORAL",
    rubric: { keywords: ["mfa", "four hours", "disable access"], threshold: "0.8000" },
    judge_model: null,
    score: "0.6667",
    threshold: "0.8000",
    status: "FAIL",
    passed: false,
    label: "Keyword coverage below threshold",
    explanation: "Measures required concepts.",
    metadata: { matched_keywords: ["mfa", "disable access"] },
    created_at: "2026-09-18T00:00:00Z",
    ...overrides
  };
}

function trace(version: string, topK: number, answer: string): Trace {
  return {
    id: `trace-${version}`,
    project_id: "project-1",
    application_version_id: version,
    external_trace_id: null,
    name: "vendor-security-question",
    status: "OK",
    input: { question: "What changed?" },
    output: { answer, retrieved_document_ids: ["policy-a"] },
    metadata: { retrieval_top_k: topK, model: "model-a", provider: "local" },
    started_at: "2026-09-18T00:00:00Z",
    ended_at: "2026-09-18T00:00:01Z",
    duration_ms: 1000,
    total_input_tokens: 10,
    total_output_tokens: 10,
    estimated_cost: null,
    error: null,
    created_at: "2026-09-18T00:00:01Z",
    spans: []
  };
}

describe("evaluation explanations", () => {
  it("explains keyword scores from matched and required concepts", () => {
    const result = explainEvaluation(evaluation());
    expect(result.calculation).toContain("2 found / 3 required = 67%");
    expect(result.missing).toEqual(["four hours"]);
  });

  it("extracts human-readable run evidence", () => {
    const run = trace("v1", 3, "Access is disabled within four hours.");
    expect(traceAnswer(run)).toContain("four hours");
    expect(retrievalIds(run)).toEqual(["policy-a"]);
  });

  it("explains a required-content failure with the actual missing requirement", () => {
    const result = explainEvaluation(evaluation({
      evaluator_name: "builtin.answer_contains",
      rubric: { expected_substring: "evaluates AI application behavior" },
      metadata: { answer: "AgentGuard monitors AI application runs." },
      score: "0.0000",
      threshold: "1.0000"
    }));
    expect(result.missing).toEqual(["evaluates AI application behavior"]);
    expect(result.calculation).toContain("found = 100%; missing = 0%");
  });

  it("derives observed runtime changes without claiming causality", () => {
    const changes = observedRuntimeChanges(trace("v1", 3, "a"), trace("v2", 6, "b"));
    expect(changes).toContainEqual({
      label: "Retrieval configuration",
      field: "retrieval_top_k",
      before: "3",
      after: "6"
    });
  });
});
