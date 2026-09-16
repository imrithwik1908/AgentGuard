import { describe, expect, it } from "vitest";

import { buildSpanTree, flattenForWaterfall } from "@/lib/trace-tree";
import type { Trace } from "@/lib/types";

const trace: Trace = {
  id: "trace-1",
  project_id: "project-1",
  application_version_id: "version-1",
  external_trace_id: "external-trace",
  name: "answer-question",
  status: "OK",
  input: null,
  output: null,
  metadata: {},
  started_at: "2026-09-12T00:00:00.000Z",
  ended_at: "2026-09-12T00:00:01.000Z",
  duration_ms: 1000,
  total_input_tokens: 1,
  total_output_tokens: 1,
  estimated_cost: null,
  error: null,
  created_at: "2026-09-12T00:00:01.000Z",
  spans: [
    {
      id: "root",
      trace_id: "trace-1",
      parent_span_id: null,
      external_span_id: "root",
      type: "RETRIEVER",
      name: "retrieve",
      status: "OK",
      input: null,
      output: null,
      metadata: {},
      attributes: {},
      provider: null,
      model_name: null,
      input_tokens: null,
      output_tokens: null,
      estimated_cost: null,
      started_at: "2026-09-12T00:00:00.100Z",
      ended_at: "2026-09-12T00:00:00.600Z",
      duration_ms: 500,
      error: null,
      created_at: "2026-09-12T00:00:00.600Z"
    },
    {
      id: "child",
      trace_id: "trace-1",
      parent_span_id: "root",
      external_span_id: "child",
      type: "TOOL",
      name: "summarize",
      status: "ERROR",
      input: null,
      output: null,
      metadata: {},
      attributes: {},
      provider: null,
      model_name: null,
      input_tokens: null,
      output_tokens: null,
      estimated_cost: null,
      started_at: "2026-09-12T00:00:00.200Z",
      ended_at: "2026-09-12T00:00:00.300Z",
      duration_ms: 100,
      error: { type: "RuntimeError", message: "boom" },
      created_at: "2026-09-12T00:00:00.300Z"
    }
  ]
};

describe("trace tree utilities", () => {
  it("builds nested span hierarchy", () => {
    const tree = buildSpanTree(trace.spans);

    expect(tree).toHaveLength(1);
    expect(tree[0].span.name).toBe("retrieve");
    expect(tree[0].children[0].span.name).toBe("summarize");
    expect(tree[0].children[0].depth).toBe(1);
  });

  it("computes waterfall offsets and widths", () => {
    const rows = flattenForWaterfall(trace);

    expect(rows[0].offsetPercent).toBeCloseTo(10);
    expect(rows[0].widthPercent).toBeCloseTo(50);
    expect(rows[1].offsetPercent).toBeCloseTo(20);
    expect(rows[1].widthPercent).toBeCloseTo(10);
  });
});

