"use client";

import type { JsonValue } from "@/lib/types";

function typeLabel(value: JsonValue): string {
  if (value === null) return "null";
  if (Array.isArray(value)) return `array[${value.length}]`;
  return typeof value;
}

export function JsonViewer({
  value,
  label = "value",
  defaultOpen = false
}: {
  value: JsonValue | null;
  label?: string;
  defaultOpen?: boolean;
}) {
  if (value === null || value === undefined) {
    return <div className="rounded bg-slate-50 px-3 py-2 text-sm text-slate-500">null</div>;
  }

  if (typeof value !== "object") {
    return <code className="rounded bg-slate-50 px-2 py-1 text-sm text-ink-900">{String(value)}</code>;
  }

  return (
    <details open={defaultOpen} className="rounded-2xl border border-slate-200 bg-slate-50">
      <summary className="cursor-pointer select-none px-3 py-2 text-xs font-medium text-slate-600">
        {label} · {typeLabel(value)}
      </summary>
      <pre className="border-t border-slate-200 p-3 text-xs leading-5 text-ink-900">
        {JSON.stringify(value, null, 2)}
      </pre>
    </details>
  );
}
