import Link from "next/link";

import { TutorialPlayer } from "@/components/tutorial-player";
import { seedDemoAction } from "../actions";

export default function TutorialPage() {
  return (
    <div className="space-y-8">
      <section className="overflow-hidden rounded-[2rem] border border-slate-200 bg-white shadow-panel">
        <div className="grid gap-0 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="p-7 md:p-8">
            <div className="text-xs font-medium uppercase tracking-[0.22em] text-cyan-700">
              Full product tutorial
            </div>
            <h1 className="mt-3 max-w-3xl text-4xl font-semibold tracking-normal text-ink-950">
              Learn the release workflow, not the database model.
            </h1>
            <p className="mt-4 max-w-3xl text-sm leading-6 text-slate-600">
              This tour follows the real job: connect an AI application, run a test suite, compare
              a candidate, investigate regressions, and decide whether to ship.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <form action={seedDemoAction}>
                <button className="rounded-full bg-ink-950 px-5 py-2.5 text-sm font-medium text-white hover:bg-ink-800">
                  Prepare demo data
                </button>
              </form>
              <Link
                className="rounded-full border border-slate-300 bg-white px-5 py-2.5 text-sm font-medium text-ink-950 hover:border-cyan-400"
                href="/traces"
              >
                Open runs
              </Link>
            </div>
          </div>
          <div className="console-surface p-7 text-white">
            <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-5">
              <div className="text-xs uppercase tracking-[0.22em] text-cyan-200">Mental model</div>
              <p className="mt-3 text-sm leading-6 text-slate-300">
                AgentGuard is not a chatbot and not just a log viewer. It watches your AI app
                change over time, connects behavior checks to runs, and turns evidence into a
                release decision.
              </p>
            </div>
          </div>
        </div>
      </section>

      <TutorialPlayer />
    </div>
  );
}
