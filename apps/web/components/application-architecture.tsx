import type {
  ArchitectureLayer,
  ObservedApplicationArchitecture
} from "@/lib/evaluation-explanations";

const layers: Array<{ id: ArchitectureLayer; label: string }> = [
  { id: "request", label: "Request" },
  { id: "orchestration", label: "Application workflow" },
  { id: "context", label: "Context and actions" },
  { id: "generation", label: "Model generation" },
  { id: "response", label: "Response" }
];

function readable(value: string): string {
  return value
    .replaceAll("_", " ")
    .replaceAll(".", " · ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function ApplicationArchitecture({
  architecture,
  highlightedLayer,
  title = "Observed application architecture"
}: {
  architecture: ObservedApplicationArchitecture;
  highlightedLayer?: ArchitectureLayer | null;
  title?: string;
}) {
  if (!architecture.nodes.length) {
    return (
      <div className="border-l-2 border-slate-200 py-2 pl-4 text-sm text-slate-600">
        Architecture appears after AgentGuard receives instrumented runs with recorded steps.
      </div>
    );
  }

  const visibleLayers = layers.filter((layer) =>
    architecture.nodes.some((node) => node.layer === layer.id)
  );
  const labelById = new Map(architecture.nodes.map((node) => [node.id, readable(node.label)]));

  return (
    <section aria-label={title}>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-700">
            Application architecture
          </div>
          <h2 className="mt-1 text-xl font-semibold text-ink-950">{title}</h2>
        </div>
        <p className="text-xs text-slate-500">
          Reconstructed from {architecture.observedRunCount} recorded {architecture.observedRunCount === 1 ? "run" : "runs"}
        </p>
      </div>

      <div className="mt-6 overflow-x-auto pb-3 [scrollbar-width:thin] lg:[scrollbar-width:none] lg:[&::-webkit-scrollbar]:hidden">
        <div className="flex min-w-max items-stretch gap-2">
          {visibleLayers.map((layer, index) => {
            const nodes = architecture.nodes.filter((node) => node.layer === layer.id);
            const highlighted = highlightedLayer === layer.id;
            return (
              <div key={layer.id} className="flex items-center gap-2">
                <div
                  className={`w-48 border bg-white p-3.5 shadow-[0_8px_24px_rgba(15,23,42,0.05)] ${
                    highlighted ? "border-amber-400 ring-4 ring-amber-100" : "border-slate-300"
                  }`}
                >
                  <div className="mb-3 flex items-center justify-between gap-2 border-b border-slate-100 pb-2">
                    <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{layer.label}</span>
                    {highlighted ? <span className="text-[10px] font-semibold uppercase text-amber-700">Difference</span> : null}
                  </div>
                  <div className="space-y-3">
                    {nodes.map((node) => (
                      <div key={node.id} className="border-l-2 border-cyan-500 pl-3">
                        <div className="text-[10px] uppercase tracking-wide text-slate-400">«{node.stereotype}»</div>
                        <div className="mt-0.5 text-sm font-semibold text-ink-950">{readable(node.label)}</div>
                        <div className="mt-1 text-xs leading-4 text-slate-500">{node.detail}</div>
                      </div>
                    ))}
                  </div>
                </div>
                {index < visibleLayers.length - 1 ? (
                  <div aria-hidden="true" className="flex w-6 items-center text-slate-400">
                    <span className="h-px flex-1 bg-slate-300" />
                    <span>›</span>
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      </div>
      {architecture.edges.length ? (
        <div className="mt-2 flex flex-wrap gap-x-5 gap-y-2 border-t border-slate-200 pt-3 text-xs text-slate-500">
          <span className="font-semibold uppercase tracking-wide text-slate-400">Observed connections</span>
          {architecture.edges.slice(0, 8).map((edge) => (
            <span key={`${edge.source}:${edge.target}`}>
              {labelById.get(edge.source) ?? edge.source} <span className="text-slate-300">→</span> {labelById.get(edge.target) ?? edge.target}
            </span>
          ))}
        </div>
      ) : null}
    </section>
  );
}
