import type { Span, Trace } from "./types";

export interface SpanNode {
  span: Span;
  children: SpanNode[];
  depth: number;
}

export interface FlatSpanNode extends SpanNode {
  offsetPercent: number;
  widthPercent: number;
}

export function buildSpanTree(spans: Span[]): SpanNode[] {
  const byId = new Map<string, SpanNode>();
  const roots: SpanNode[] = [];

  for (const span of spans) {
    byId.set(span.id, { span, children: [], depth: 0 });
  }

  for (const node of byId.values()) {
    if (node.span.parent_span_id && byId.has(node.span.parent_span_id)) {
      const parent = byId.get(node.span.parent_span_id)!;
      node.depth = parent.depth + 1;
      parent.children.push(node);
    } else {
      roots.push(node);
    }
  }

  const sortNodes = (nodes: SpanNode[]) => {
    nodes.sort(
      (a, b) =>
        new Date(a.span.started_at).getTime() - new Date(b.span.started_at).getTime() ||
        a.span.name.localeCompare(b.span.name)
    );
    for (const node of nodes) {
      for (const child of node.children) {
        child.depth = node.depth + 1;
      }
      sortNodes(node.children);
    }
  };

  sortNodes(roots);
  return roots;
}

export function flattenSpanTree(nodes: SpanNode[]): SpanNode[] {
  return nodes.flatMap((node) => [node, ...flattenSpanTree(node.children)]);
}

export function timelineBounds(trace: Trace): { start: number; end: number; duration: number } {
  const traceStart = new Date(trace.started_at).getTime();
  const traceEnd = new Date(trace.ended_at).getTime();
  const spanEnd = Math.max(
    traceEnd,
    ...trace.spans.map((span) => new Date(span.ended_at).getTime())
  );
  const end = Math.max(traceStart + 1, spanEnd);
  return { start: traceStart, end, duration: Math.max(1, end - traceStart) };
}

export function flattenForWaterfall(trace: Trace): FlatSpanNode[] {
  const bounds = timelineBounds(trace);
  return flattenSpanTree(buildSpanTree(trace.spans)).map((node) => {
    const spanStart = new Date(node.span.started_at).getTime();
    const spanEnd = new Date(node.span.ended_at).getTime();
    const offsetPercent = Math.max(0, ((spanStart - bounds.start) / bounds.duration) * 100);
    const widthPercent = Math.max(0.8, ((Math.max(spanEnd, spanStart + 1) - spanStart) / bounds.duration) * 100);
    return { ...node, offsetPercent: Math.min(100, offsetPercent), widthPercent: Math.min(100, widthPercent) };
  });
}

