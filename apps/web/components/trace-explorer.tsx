"use client";

import clsx from "clsx";
import { useMemo, useState } from "react";

import { formatCost, formatDateTime, formatDuration } from "@/lib/format";
import { flattenForWaterfall } from "@/lib/trace-tree";
import type { ApplicationVersion, Project, Span, Trace } from "@/lib/types";

import { JsonViewer } from "./json-viewer";
import { StatusBadge } from "./status-badge";

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-1 text-sm text-ink-950">{value ?? "—"}</dd>
    </div>
  );
}

function SpanTypeBadge({ type }: { type: string }) {
  return (
    <span className="rounded border border-slate-200 bg-white px-1.5 py-0.5 text-[11px] font-medium text-slate-600">
      {type}
    </span>
  );
}

function spanTypeMeaning(type: string): string {
  if (type === "LLM") return "Model call";
  if (type === "RETRIEVER") return "Retrieved context";
  if (type === "TOOL") return "Tool/action";
  if (type === "AGENT") return "Agent workflow";
  if (type === "EMBEDDING") return "Embedding step";
  if (type === "RERANKER") return "Ranking step";
  if (type === "CHAIN") return "Application chain";
  return "Custom operation";
}

function spanStatusMeaning(span: Span): string {
  if (span.status === "ERROR") {
    return "This step captured an error. Open the error evidence below to see what failed.";
  }
  if (span.output !== null && span.output !== undefined) {
    return "This step completed and recorded output evidence.";
  }
  if (span.input !== null && span.input !== undefined) {
    return "This step completed and recorded input evidence.";
  }
  return "This step completed, but it did not record detailed input or output payloads.";
}

export function TraceExplorer({
  trace,
  project,
  version
}: {
  trace: Trace;
  project: Project;
  version: ApplicationVersion | null;
}) {
  const waterfall = useMemo(() => flattenForWaterfall(trace), [trace]);
  const [selectedSpanId, setSelectedSpanId] = useState<string | null>(waterfall[0]?.span.id ?? null);
  const selectedSpan = trace.spans.find((span) => span.id === selectedSpanId) ?? waterfall[0]?.span ?? null;
  const spanById = new Map(trace.spans.map((span) => [span.id, span]));
  const rootSpanCount = trace.spans.filter((span) => span.parent_span_id === null).length;
  const errorSpanCount = trace.spans.filter((span) => span.status === "ERROR").length;

  return (
    <div className="space-y-5">
      <section className="overflow-hidden rounded-[2rem] border border-slate-200 bg-white shadow-panel">
        <div className="h-1 bg-gradient-to-r from-cyan-500 via-emerald-500 to-red-500" />
        <div className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <StatusBadge status={trace.status} />
              <span className="text-xs text-slate-500">{project.name}</span>
              <span className="text-xs text-slate-400">/</span>
              <span className="text-xs text-slate-500">{version?.version ?? trace.application_version_id}</span>
            </div>
            <h1 className="mt-3 text-2xl font-semibold text-ink-950">{trace.name}</h1>
            <p className="mt-1 font-mono text-xs text-slate-500">
              {trace.external_trace_id ?? trace.id}
            </p>
          </div>
        </div>

        <dl className="mt-5 grid gap-4 md:grid-cols-4 xl:grid-cols-7">
          <Field label="Started" value={formatDateTime(trace.started_at)} />
          <Field label="Duration" value={formatDuration(trace.duration_ms)} />
          <Field label="Input tokens" value={trace.total_input_tokens ?? "—"} />
          <Field label="Output tokens" value={trace.total_output_tokens ?? "—"} />
          <Field label="Cost" value={formatCost(trace.estimated_cost)} />
          <Field label="Steps" value={trace.spans.length} />
          <Field label="Run ID" value={<span className="font-mono text-xs">{trace.id}</span>} />
        </dl>
        </div>
      </section>

      <section className="grid gap-3 md:grid-cols-3">
        <div className="rounded-2xl border border-cyan-200 bg-cyan-50/70 p-4 shadow-panel">
          <div className="text-xs font-medium uppercase tracking-wide text-cyan-700">Debugging details</div>
          <p className="mt-2 text-sm leading-6 text-slate-700">
            This is the technical view for one run. The rows below are internal steps recorded by the SDK.
          </p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-panel">
          <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Root steps</div>
          <div className="mt-2 text-2xl font-semibold text-ink-950">{rootSpanCount}</div>
          <p className="mt-1 text-sm text-slate-600">Top-level operations in this run.</p>
        </div>
        <div className="rounded-2xl border border-red-200 bg-red-50/70 p-4 shadow-panel">
          <div className="text-xs font-medium uppercase tracking-wide text-red-700">Error steps</div>
          <div className="mt-2 text-2xl font-semibold text-red-950">{errorSpanCount}</div>
          <p className="mt-1 text-sm text-red-800">Steps that captured an exception or failure status.</p>
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(360px,0.65fr)]">
        <section className="overflow-hidden rounded-[2rem] border border-slate-200 bg-white shadow-panel">
          <div className="border-b border-slate-200 bg-slate-50 px-4 py-3">
            <div className="grid grid-cols-[minmax(280px,0.9fr)_minmax(240px,1.1fr)] text-xs font-medium uppercase tracking-wide text-slate-500">
              <div>Step hierarchy</div>
              <div>Timing waterfall</div>
            </div>
            <p className="mt-2 text-xs text-slate-500">
              Indentation shows nesting. Bar position and width show timing relative to the whole run.
            </p>
            <div className="mt-3 grid grid-cols-4 text-[11px] text-slate-400">
              <span>0%</span>
              <span>25%</span>
              <span>50%</span>
              <span className="text-right">100%</span>
            </div>
          </div>

          {waterfall.length === 0 ? (
            <div className="p-8 text-sm text-slate-600">This run has no recorded steps.</div>
          ) : (
            <div role="tree" aria-label="Run steps" className="divide-y divide-slate-100">
              {waterfall.map((node) => {
                const span = node.span;
                const selected = span.id === selectedSpan?.id;
                return (
                  <button
                    key={span.id}
                    type="button"
                    role="treeitem"
                    aria-selected={selected}
                    onClick={() => setSelectedSpanId(span.id)}
                    className={clsx(
                      "grid w-full grid-cols-[minmax(280px,0.9fr)_minmax(240px,1.1fr)] items-center gap-4 px-4 py-3 text-left transition",
                      selected && "bg-slate-100",
                      !selected && "hover:bg-slate-50"
                    )}
                  >
                    <div className="flex min-w-0 items-center gap-2" style={{ paddingLeft: node.depth * 18 }}>
                      <span
                        className={clsx(
                          "h-2 w-2 shrink-0 rounded-full",
                          span.status === "ERROR" ? "bg-signal-error" : "bg-signal-ok"
                        )}
                      />
                      <span className="truncate text-sm font-medium text-ink-950">{span.name}</span>
                      <SpanTypeBadge type={span.type} />
                      <span className="text-xs text-slate-500">{formatDuration(span.duration_ms)}</span>
                    </div>
                    <div className="relative h-8 overflow-hidden rounded-full bg-slate-100">
                      <div className="absolute inset-y-0 left-1/4 w-px bg-white" />
                      <div className="absolute inset-y-0 left-1/2 w-px bg-white" />
                      <div className="absolute inset-y-0 left-3/4 w-px bg-white" />
                      <div
                        className={clsx(
                          "absolute top-1 h-6 min-w-2 rounded-full transition-all",
                          span.status === "ERROR" ? "bg-red-500 shadow-[0_0_18px_rgba(239,68,68,0.35)]" : "bg-emerald-500 shadow-[0_0_18px_rgba(16,185,129,0.25)]"
                        )}
                        style={{
                          left: `${node.offsetPercent}%`,
                          width: `${node.widthPercent}%`
                        }}
                      />
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </section>

        <aside className="overflow-hidden rounded-[2rem] border border-slate-200 bg-white shadow-panel">
          <div className="border-b border-slate-200 px-4 py-3">
            <h2 className="text-sm font-semibold text-ink-950">Step details</h2>
          </div>
          {selectedSpan ? (
            <SpanDetails span={selectedSpan} parent={selectedSpan.parent_span_id ? spanById.get(selectedSpan.parent_span_id) ?? null : null} />
          ) : (
            <div className="p-4 text-sm text-slate-600">Select a step to inspect its data.</div>
          )}
        </aside>
      </div>
    </div>
  );
}

function SpanDetails({ span, parent }: { span: Span; parent: Span | null }) {
  const hasInput = span.input !== null && span.input !== undefined;
  const hasOutput = span.output !== null && span.output !== undefined;
  const hasMetadata = Object.keys(span.metadata ?? {}).length > 0 || Object.keys(span.attributes ?? {}).length > 0;

  return (
    <div className="space-y-5 p-4">
      <section
        className={clsx(
          "rounded-2xl border p-4",
          span.status === "ERROR"
            ? "border-red-200 bg-red-50 text-red-950"
            : "border-emerald-200 bg-emerald-50 text-emerald-950"
        )}
      >
        <div className="text-xs font-semibold uppercase tracking-[0.18em] opacity-70">
          Selected step
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span className="text-lg font-semibold">{span.name}</span>
          <SpanTypeBadge type={span.type} />
        </div>
        <p className="mt-2 text-sm leading-6 opacity-85">{spanStatusMeaning(span)}</p>
        <div className="mt-3 grid gap-2 text-xs sm:grid-cols-3">
          <div className="rounded-xl bg-white/70 p-3">
            <div className="font-semibold">{spanTypeMeaning(span.type)}</div>
            <div className="mt-1 opacity-70">What kind of work this step did.</div>
          </div>
          <div className="rounded-xl bg-white/70 p-3">
            <div className="font-semibold">{formatDuration(span.duration_ms)}</div>
            <div className="mt-1 opacity-70">Time spent in this step.</div>
          </div>
          <div className="rounded-xl bg-white/70 p-3">
            <div className="font-semibold">
              {[hasInput && "input", hasOutput && "output", hasMetadata && "metadata"]
                .filter(Boolean)
                .join(" + ") || "timing only"}
            </div>
            <div className="mt-1 opacity-70">Evidence captured by the SDK.</div>
          </div>
        </div>
      </section>

      <dl className="grid grid-cols-2 gap-4">
        <Field label="Name" value={span.name} />
        <Field label="Status" value={<StatusBadge status={span.status} />} />
        <Field label="Type" value={span.type} />
        <Field label="Parent" value={parent?.name ?? "Root step"} />
        <Field label="Started" value={formatDateTime(span.started_at)} />
        <Field label="Ended" value={formatDateTime(span.ended_at)} />
        <Field label="Duration" value={formatDuration(span.duration_ms)} />
        <Field label="Provider" value={span.provider ?? "—"} />
        <Field label="Model" value={span.model_name ?? "—"} />
        <Field label="Input tokens" value={span.input_tokens ?? "—"} />
        <Field label="Output tokens" value={span.output_tokens ?? "—"} />
        <Field label="Cost" value={formatCost(span.estimated_cost)} />
      </dl>

      <div className="space-y-3">
        {span.error ? (
          <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-900">
            <div className="font-medium">{String(span.error.type ?? "Error")}</div>
            <div className="mt-1 text-red-800">{String(span.error.message ?? "No message recorded")}</div>
          </div>
        ) : null}
        <JsonViewer label="input" value={span.input} defaultOpen={span.status === "ERROR"} />
        <JsonViewer label="output" value={span.output} />
        <JsonViewer label="metadata" value={span.metadata} />
        <JsonViewer label="attributes" value={span.attributes} />
        {span.error ? <JsonViewer label="error" value={span.error} defaultOpen /> : null}
      </div>

      <div className="rounded bg-slate-50 p-3">
        <div className="text-xs uppercase tracking-wide text-slate-500">Step ID</div>
        <div className="mt-1 break-all font-mono text-xs text-slate-700">{span.id}</div>
      </div>
    </div>
  );
}
