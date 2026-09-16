import clsx from "clsx";

import type { EvaluationStatus } from "@/lib/types";

const styles: Record<EvaluationStatus, string> = {
  PASS: "border-emerald-200 bg-emerald-50 text-emerald-700",
  FAIL: "border-red-200 bg-red-50 text-red-700",
  ERROR: "border-amber-200 bg-amber-50 text-amber-700"
};

export function EvaluationStatusBadge({ status }: { status: EvaluationStatus }) {
  return (
    <span className={clsx("inline-flex items-center rounded border px-2 py-0.5 text-xs font-medium", styles[status])}>
      {status}
    </span>
  );
}
