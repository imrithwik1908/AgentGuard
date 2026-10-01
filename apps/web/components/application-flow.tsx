import type { ApplicationStage, ObservedApplicationStage } from "@/lib/evaluation-explanations";

export function ApplicationFlow({
  stages,
  highlightedStage,
  title = "Observed application flow"
}: {
  stages: ObservedApplicationStage[];
  highlightedStage?: ApplicationStage | null;
  title?: string;
}) {
  if (!stages.length) {
    return (
      <div className="border-l-2 border-slate-200 py-2 pl-4 text-sm text-slate-600">
        The application flow will appear after AgentGuard receives an instrumented run.
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-end justify-between gap-4">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-cyan-700">Application map</div>
          <h2 className="mt-1 text-lg font-semibold text-ink-950">{title}</h2>
        </div>
        <div className="hidden text-xs text-slate-500 sm:block">Built from recorded run steps</div>
      </div>
      <div className="mt-5 overflow-x-auto pb-2">
        <ol className="flex min-w-max items-start">
          {stages.map((stage, index) => {
            const highlighted = stage.id === highlightedStage;
            const errored = stage.status === "ERROR";
            return (
              <li key={stage.id} className="flex items-start">
                <div className="w-40">
                  <div className="flex items-center">
                    <span
                      className={`h-3 w-3 rounded-full ring-4 ${
                        highlighted
                          ? "bg-amber-500 ring-amber-100"
                          : errored
                            ? "bg-red-500 ring-red-100"
                            : "bg-cyan-600 ring-cyan-50"
                      }`}
                    />
                    {index < stages.length - 1 ? <span className="h-px flex-1 bg-slate-200" /> : null}
                  </div>
                  <div className={`mt-3 pr-5 ${highlighted ? "text-amber-900" : "text-ink-950"}`}>
                    <div className="text-sm font-semibold">{stage.label}</div>
                    <div className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">{stage.detail}</div>
                    {highlighted ? (
                      <div className="mt-2 text-xs font-medium text-amber-700">First supported difference</div>
                    ) : null}
                  </div>
                </div>
              </li>
            );
          })}
        </ol>
      </div>
    </div>
  );
}
