import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { describe, expect, it } from "vitest";

import { TraceExplorer } from "@/components/trace-explorer";
import type { ApplicationVersion, Project, Trace } from "@/lib/types";

const project: Project = {
  id: "project-1",
  workspace_id: null,
  name: "Research Agent",
  slug: "research-agent",
  description: null,
  created_at: "2026-09-12T00:00:00.000Z",
  updated_at: "2026-09-12T00:00:00.000Z"
};

const version: ApplicationVersion = {
  id: "version-1",
  project_id: "project-1",
  name: "Initial",
  version: "v1",
  git_commit: null,
  model_config: {},
  prompt_config: {},
  retrieval_config: {},
  agent_config: {},
  metadata: {},
  created_at: "2026-09-12T00:00:00.000Z"
};

const trace: Trace = {
  id: "trace-1",
  project_id: "project-1",
  application_version_id: "version-1",
  external_trace_id: "external-trace",
  name: "answer-question",
  status: "ERROR",
  input: null,
  output: null,
  metadata: {},
  started_at: "2026-09-12T00:00:00.000Z",
  ended_at: "2026-09-12T00:00:01.000Z",
  duration_ms: 1000,
  total_input_tokens: 10,
  total_output_tokens: 5,
  estimated_cost: null,
  error: null,
  created_at: "2026-09-12T00:00:01.000Z",
  spans: [
    {
      id: "retrieve",
      trace_id: "trace-1",
      parent_span_id: null,
      external_span_id: "retrieve",
      type: "RETRIEVER",
      name: "retrieve",
      status: "OK",
      input: { query: "AgentGuard" },
      output: {},
      metadata: {},
      attributes: {},
      provider: null,
      model_name: null,
      input_tokens: null,
      output_tokens: null,
      estimated_cost: null,
      started_at: "2026-09-12T00:00:00.100Z",
      ended_at: "2026-09-12T00:00:00.500Z",
      duration_ms: 400,
      error: null,
      created_at: "2026-09-12T00:00:00.500Z"
    },
    {
      id: "generate",
      trace_id: "trace-1",
      parent_span_id: null,
      external_span_id: "generate",
      type: "LLM",
      name: "generate",
      status: "ERROR",
      input: {},
      output: null,
      metadata: {},
      attributes: {},
      provider: null,
      model_name: null,
      input_tokens: null,
      output_tokens: null,
      estimated_cost: null,
      started_at: "2026-09-12T00:00:00.600Z",
      ended_at: "2026-09-12T00:00:00.900Z",
      duration_ms: 300,
      error: { type: "RuntimeError", message: "boom" },
      created_at: "2026-09-12T00:00:00.900Z"
    }
  ]
};

describe("TraceExplorer", () => {
  it("renders nested rows, failed span state, and selectable details", async () => {
    render(<TraceExplorer trace={trace} project={project} version={version} />);

    expect(screen.getByText("answer-question")).toBeInTheDocument();
    expect(screen.getByRole("treeitem", { name: /retrieve/i })).toBeInTheDocument();
    expect(screen.getByRole("treeitem", { name: /generate/i })).toBeInTheDocument();
    expect(screen.getAllByText("ERROR").length).toBeGreaterThan(0);

    await userEvent.click(screen.getByRole("treeitem", { name: /generate/i }));

    expect(screen.getByText("RuntimeError")).toBeInTheDocument();
    expect(screen.getAllByText(/boom/).length).toBeGreaterThan(0);
  });

  it("handles empty metadata and empty spans", () => {
    render(<TraceExplorer trace={{ ...trace, spans: [] }} project={project} version={version} />);

    expect(screen.getByText("This run has no recorded steps.")).toBeInTheDocument();
    expect(screen.getByText("Select a step to inspect its data.")).toBeInTheDocument();
  });
});
