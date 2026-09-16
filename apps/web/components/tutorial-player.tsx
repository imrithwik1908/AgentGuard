"use client";

import clsx from "clsx";
import { useMemo, useState } from "react";

const steps = [
  {
    title: "Connect an AI application",
    action: "Create a project and install the SDK",
    userView: "Your app starts sending runs to AgentGuard without changing the user-facing app flow.",
    backend: ["Create project/version", "SDK opens trace context", "SDK records spans", "POST /api/v1/traces"],
    focus: "Setup"
  },
  {
    title: "Create or use a test suite",
    action: "Add expected behaviors",
    userView: "A suite stores important questions, requirements, and expected outputs to protect.",
    backend: ["POST /api/v1/datasets", "Store cases", "Validate expectations", "Make cases runnable"],
    focus: "Test Suites"
  },
  {
    title: "Establish a baseline",
    action: "Run checks on the trusted version",
    userView: "AgentGuard stores pass/fail results and scores for the version you trust today.",
    backend: ["Run dataset case", "Create trace", "Store evaluation", "Summarize version quality"],
    focus: "Baseline"
  },
  {
    title: "Evaluate a candidate change",
    action: "Run the same suite on the changed version",
    userView: "Now AgentGuard can compare behavior instead of showing isolated metrics.",
    backend: ["Resolve candidate version", "Run same cases", "Persist new traces", "Persist new evaluations"],
    focus: "Candidate"
  },
  {
    title: "Review regressions first",
    action: "Open Releases",
    userView: "Regressed cases appear before averages, because failures decide whether the change is safe.",
    backend: ["Pair evaluations by case", "Bucket regressed/improved/unchanged", "Calculate deltas", "Link failed runs"],
    focus: "Regressions"
  },
  {
    title: "Investigate one failure",
    action: "Open the failed run",
    userView: "You see what failed first, then drill into the waterfall and span details only if needed.",
    backend: ["GET /api/v1/traces/{id}", "Load spans", "Build waterfall", "Expose raw payloads in details"],
    focus: "Investigation"
  },
  {
    title: "Make a release decision",
    action: "Ship, review, or block",
    userView: "The release decision uses stored evidence and clear thresholds, not vibes.",
    backend: ["Aggregate summaries", "Apply thresholds", "Return PASS/REVIEW/BLOCK", "CI can consume same decision"],
    focus: "Decision"
  }
];

export function TutorialPlayer() {
  const [index, setIndex] = useState(0);
  const step = steps[index];
  const progress = useMemo(() => ((index + 1) / steps.length) * 100, [index]);

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1.1fr)_minmax(360px,0.9fr)]">
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

      <aside className="console-surface rounded-[2rem] p-5 text-white shadow-panel">
        <div className="text-xs font-medium uppercase tracking-[0.22em] text-emerald-200">
          Backend grunt work
        </div>
        <h2 className="mt-2 text-2xl font-semibold">What AgentGuard is doing underneath</h2>
        <div className="mt-6 space-y-4">
          {step.backend.map((item, itemIndex) => (
            <div key={item} className="flex gap-3">
              <div className="relative flex w-8 justify-center">
                <div className="grid h-8 w-8 place-items-center rounded-full border border-emerald-300/60 bg-emerald-300/10 text-xs text-emerald-100">
                  {itemIndex + 1}
                </div>
                {itemIndex < step.backend.length - 1 ? (
                  <div className="absolute top-8 h-8 w-px bg-emerald-300/30" />
                ) : null}
              </div>
              <div className="pt-1">
                <div className="text-sm font-medium">{item}</div>
                <div className="mt-1 h-1.5 w-40 overflow-hidden rounded-full bg-white/10">
                  <div
                    className="h-full rounded-full bg-emerald-300 transition-all"
                    style={{ width: `${Math.max(28, (itemIndex + 1) * 24)}%` }}
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
        <p className="mt-6 text-sm leading-6 text-slate-300">
          Backend mechanics are shown as supporting context. The main path stays centered on the
          user's release question: did the change improve behavior, regress, or need review?
        </p>
      </aside>
    </div>
  );
}
