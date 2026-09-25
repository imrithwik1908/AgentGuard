"use client";

export default function ErrorPage({
  error,
  reset
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <section className="mx-auto max-w-2xl overflow-hidden rounded-2xl border border-amber-200 bg-white shadow-panel">
      <div className="h-1 bg-amber-400" />
      <div className="p-6 sm:p-8">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-amber-700">
        Temporary connection issue
      </p>
      <h1 className="mt-2 text-xl font-semibold text-slate-950">This view did not finish loading</h1>
      <p className="mt-2 text-sm leading-6 text-slate-600">
        AgentGuard may still be reconnecting to the API. Wait a moment, then try again.
      </p>
      <button
        type="button"
        onClick={reset}
        className="mt-5 rounded-full bg-slate-950 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-cyan-800 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:ring-offset-2"
      >
        Try again
      </button>
      <details className="mt-5">
        <summary className="cursor-pointer text-sm font-medium text-slate-500">
          Technical details
        </summary>
        <pre className="mt-2 max-w-full overflow-x-auto rounded-lg bg-slate-100 p-3 text-xs text-slate-700">
          {error.message}
        </pre>
      </details>
      </div>
    </section>
  );
}
