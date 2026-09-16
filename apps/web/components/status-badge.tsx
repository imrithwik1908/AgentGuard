import clsx from "clsx";

import type { RunStatus } from "@/lib/types";

export function StatusBadge({ status }: { status: RunStatus }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded border px-2 py-0.5 text-xs font-medium",
        status === "OK" && "border-emerald-200 bg-emerald-50 text-emerald-700",
        status === "ERROR" && "border-red-200 bg-red-50 text-red-700",
        status === "UNSET" && "border-slate-200 bg-slate-50 text-slate-600"
      )}
    >
      {status}
    </span>
  );
}

