import Link from "next/link";

import { TutorialPlayer } from "@/components/tutorial-player";
import { seedDemoAction } from "../actions";

export default function TutorialPage() {
  return (
    <div className="space-y-8">
      <section className="border-b border-slate-200 pb-8">
        <div className="text-xs font-medium uppercase tracking-[0.22em] text-cyan-700">
          Product tutorial
        </div>
        <h1 className="mt-3 max-w-3xl text-4xl font-semibold tracking-normal text-ink-950">
          Follow a change from setup to release.
        </h1>
        <p className="mt-4 max-w-3xl text-sm leading-6 text-slate-600">
          Connect an AI application, run a test suite, compare a candidate, investigate regressions,
          and review the release decision.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <form action={seedDemoAction}>
            <button className="rounded-full bg-ink-950 px-5 py-2.5 text-sm font-medium text-white hover:bg-ink-800">
              Load example workspace
            </button>
          </form>
          <Link
            className="rounded-full border border-slate-300 bg-white px-5 py-2.5 text-sm font-medium text-ink-950 hover:border-cyan-400"
            href="/traces"
          >
            Open runs
          </Link>
        </div>
      </section>

      <TutorialPlayer />
    </div>
  );
}
