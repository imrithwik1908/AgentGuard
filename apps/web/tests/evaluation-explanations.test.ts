import { describe, expect, it } from "vitest";

import {
  explainEvaluation,
  firstSupportedDifference,
  observedApplicationArchitecture,
  observedApplicationFlow,
  observedRuntimeChanges,
  retrievalIds,
  traceAnswer
} from "@/lib/evaluation-explanations";
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

  it("builds an application flow only from recorded spans", () => {
    const run = trace("v1", 3, "A supported answer");
    run.spans = [
      {
        id: "span-retrieval",
        trace_id: run.id,
        parent_span_id: null,
        external_span_id: null,
        type: "RETRIEVER",
        name: "search meeting notes",
        status: "OK",
        input: null,
        output: { documents: [{ id: "notes-1" }] },
        metadata: {},
        attributes: {},
        provider: null,
        model_name: null,
        input_tokens: null,
        output_tokens: null,
        estimated_cost: null,
        started_at: "2026-09-18T00:00:00Z",
        ended_at: "2026-09-18T00:00:00.100Z",
        duration_ms: 100,
        error: null,
        created_at: "2026-09-18T00:00:00.100Z"
      },
      {
        id: "span-model",
        trace_id: run.id,
        parent_span_id: null,
        external_span_id: null,
        type: "LLM",
        name: "generate answer",
        status: "OK",
        input: null,
        output: { answer: "A supported answer" },
        metadata: {},
        attributes: {},
        provider: "test",
        model_name: "judge-test",
        input_tokens: 10,
        output_tokens: 5,
        estimated_cost: null,
        started_at: "2026-09-18T00:00:00.100Z",
        ended_at: "2026-09-18T00:00:00.500Z",
        duration_ms: 400,
        error: null,
        created_at: "2026-09-18T00:00:00.500Z"
      }
    ];

    expect(observedApplicationFlow(run).map((stage) => stage.id)).toEqual([
      "input",
      "retrieval",
      "generation",
      "output"
    ]);

    const architecture = observedApplicationArchitecture([run]);
    expect(architecture.observedRunCount).toBe(1);
    expect(architecture.nodes.map((node) => [node.layer, node.label])).toEqual([
      ["request", "Application request"],
      ["context", "search meeting notes"],
      ["generation", "generate answer"],
      ["response", "Application response"]
    ]);
    expect(architecture.edges).toEqual(expect.arrayContaining([
      { source: "request", target: expect.stringContaining("RETRIEVER:search meeting notes") },
      { source: expect.stringContaining("LLM:generate answer"), target: "response" }
    ]));
  });

  it("merges repeated observed components across runs", () => {
    const first = trace("v1", 3, "a");
    const second = trace("v2", 6, "b");
    const modelSpan = {
      id: "model-1",
      trace_id: first.id,
      parent_span_id: null,
      external_span_id: null,
      type: "LLM" as const,
      name: "generate answer",
      status: "OK" as const,
      input: null,
      output: { answer: "answer" },
      metadata: {},
      attributes: {},
      provider: "local",
      model_name: "small-model",
      input_tokens: 10,
      output_tokens: 5,
      estimated_cost: null,
      started_at: "2026-09-18T00:00:00Z",
      ended_at: "2026-09-18T00:00:00.500Z",
      duration_ms: 500,
      error: null,
      created_at: "2026-09-18T00:00:00.500Z"
    };
    first.spans = [modelSpan];
    second.spans = [{ ...modelSpan, id: "model-2", trace_id: second.id }];

    const architecture = observedApplicationArchitecture([first, second]);
    expect(architecture.nodes.find((node) => node.layer === "generation")?.observedRuns).toBe(2);
  });

  it("highlights the earliest supported failed evaluation stage", () => {
    expect(firstSupportedDifference([
      evaluation({ evaluator_name: "builtin.keyword_coverage", passed: false }),
      evaluation({ id: "evaluation-2", evaluator_name: "builtin.required_source", passed: false })
    ])).toBe("retrieval");
  });
});
