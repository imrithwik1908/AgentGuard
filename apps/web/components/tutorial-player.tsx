"use client";

import clsx from "clsx";
import { useMemo, useState } from "react";

const steps = [
  {
    title: "Connect an AI application",
    action: "Create a project and install the SDK",
    userView: "Your app starts sending runs to AgentGuard without changing the user-facing app flow.",
    focus: "Setup"
  },
  {
    title: "Create or use a test suite",
    action: "Add expected behaviors",
    userView: "A suite stores important questions, requirements, and expected outputs to protect.",
    focus: "Test Suites"
  },
  {
    title: "Establish a baseline",
    action: "Run checks on the trusted version",
    userView: "AgentGuard stores pass/fail results and scores for the version you trust today.",
    focus: "Baseline"
  },
  {
    title: "Evaluate a candidate change",
    action: "Run the same suite on the changed version",
    userView: "Now AgentGuard can compare behavior instead of showing isolated metrics.",
    focus: "Candidate"
  },
  {
    title: "Review regressions first",
    action: "Open Releases",
    userView: "Regressed cases appear before averages, because failures decide whether the change is safe.",
    focus: "Regressions"
  },
  {
    title: "Investigate one failure",
    action: "Open the failed run",
    userView: "You see what failed first, then drill into the waterfall and span details only if needed.",
    focus: "Investigation"
  },
  {
    title: "Make a release decision",
    action: "Ship, review, or block",
    userView: "The release decision uses stored evidence and configured thresholds.",
    focus: "Decision"
  }
];

export function TutorialPlayer() {
  const [index, setIndex] = useState(0);
  const step = steps[index];
  const progress = useMemo(() => ((index + 1) / steps.length) * 100, [index]);

  return (
    <div className="mx-auto max-w-5xl">
      <section className="overflow-hidden rounded-[2rem] border border-slate-200 bg-white shadow-panel">
        <div className="border-b border-slate-200 bg-slate-50 p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-xs font-medium uppercase tracking-[0.22em] text-cyan-700">
                Guided product tour
              </div>
              <h2 className="mt-2 text-2xl font-semibold text-ink-950">{step.title}</h2>
            </div>
            <div className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs text-slate-600">
              {index + 1} / {steps.length}
            </div>
          </div>
          <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-200">
            <div className="h-full rounded-full bg-cyan-600 transition-all" style={{ width: `${progress}%` }} />
          </div>
        </div>

        <div className="p-5">
          <div className="rounded-[1.5rem] border border-slate-200 bg-slate-950 p-4 text-white">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-xs uppercase tracking-[0.22em] text-slate-400">Paused demo screen</div>
                <div className="mt-2 text-lg font-semibold">{step.focus}</div>
              </div>
              <div className="rounded-full bg-cyan-300 px-3 py-1 text-xs font-medium text-ink-950">Paused</div>
            </div>

            <div className="mt-5 grid gap-3 md:grid-cols-[0.8fr_1.2fr]">
              <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                <div className="text-xs uppercase tracking-[0.2em] text-cyan-200">Do this</div>
                <div className="step-pulse mt-4 rounded-xl bg-cyan-300 px-4 py-3 text-sm font-semibold text-ink-950">
                  {step.action}
                </div>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                <div className="text-xs uppercase tracking-[0.2em] text-cyan-200">What you should notice</div>
                <p className="mt-4 text-sm leading-6 text-slate-200">{step.userView}</p>
              </div>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {steps.map((candidate, candidateIndex) => (
              <button
                key={candidate.title}
                type="button"
                onClick={() => setIndex(candidateIndex)}
                className={clsx(
                  "rounded-full px-3 py-2 text-sm transition",
                  candidateIndex === index
                    ? "bg-ink-950 text-white"
                    : "border border-slate-200 bg-white text-slate-700 hover:border-cyan-400"
                )}
              >
                {candidateIndex + 1}. {candidate.focus}
              </button>
            ))}
          </div>

          <div className="mt-5 flex justify-between">
            <button
              type="button"
              onClick={() => setIndex(Math.max(0, index - 1))}
              disabled={index === 0}
              className="rounded-full border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Back
            </button>
            <button
              type="button"
              onClick={() => setIndex(Math.min(steps.length - 1, index + 1))}
              disabled={index === steps.length - 1}
              className="rounded-full bg-ink-950 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
