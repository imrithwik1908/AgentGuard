import Link from "next/link";

export function ProductStatus() {
  return (
    <section className="surface rounded-[2rem] p-5">
      <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs font-medium uppercase tracking-[0.2em] text-cyan-700">
            Current product checkpoint
          </div>
          <h2 className="mt-2 text-xl font-semibold text-ink-950">
            AgentGuard checks whether AI application changes are safe to ship.
          </h2>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            This build records complete executions from the Python SDK, stores each nested step in
            PostgreSQL, runs deterministic checks from test suites, compares versions, and produces
            release decisions. Richer semantic, retrieval, and tool-behavior evaluators are designed
            as future additions rather than shown as if they already exist.
          </p>
        </div>
        <div className="min-w-[22rem] space-y-2 text-sm">
          {[
            ["Connect", "Instrument an AI app or run the deterministic demo agent."],
            ["Evaluate", "Run behavioral test-suite cases against a version."],
            ["Compare", "Review candidate behavior against a baseline."],
            ["Investigate", "Open run internals only when a regression needs debugging."]
          ].map(([label, text]) => (
            <div key={label} className="flex gap-3 rounded-2xl bg-slate-50/90 px-3 py-2">
              <div className="mt-1 h-2 w-2 shrink-0 rounded-full bg-cyan-600" />
              <div>
                <div className="font-medium text-ink-950">{label}</div>
                <div className="mt-1 text-slate-600">{text}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="mt-5 flex flex-wrap gap-3">
        <Link className="rounded-full bg-ink-900 px-4 py-2 text-sm font-medium text-white hover:bg-ink-800" href="/traces">
          Inspect runs
        </Link>
        <Link
          className="rounded-full border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          href="/projects"
        >
          Manage projects
        </Link>
        <Link
          className="rounded-full border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          href="/datasets"
        >
          Run test suites
        </Link>
        <Link
          className="rounded-full border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          href="/releases"
        >
          Review releases
        </Link>
      </div>
    </section>
  );
}
