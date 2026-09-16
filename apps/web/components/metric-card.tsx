import clsx from "clsx";

export function MetricCard({
  label,
  value,
  detail,
  tone = "neutral"
}: {
  label: string;
  value: string | number;
  detail?: string;
  tone?: "neutral" | "ok" | "error" | "focus";
}) {
  return (
    <div
      className={clsx(
        "flex-1 rounded-[1.25rem] p-4 transition duration-200 hover:-translate-y-0.5",
        tone === "neutral" && "bg-white/70",
        tone === "ok" && "bg-emerald-50/80",
        tone === "error" && "bg-red-50/80",
        tone === "focus" && "bg-cyan-50/80"
      )}
    >
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-ink-950">{value}</div>
      {detail ? <div className="mt-1 text-sm text-slate-600">{detail}</div> : null}
    </div>
  );
}
