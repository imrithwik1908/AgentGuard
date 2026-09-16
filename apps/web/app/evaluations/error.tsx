"use client";

export default function Error({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <section className="rounded border border-red-200 bg-red-50 p-6 text-red-900">
      <h1 className="text-lg font-semibold">Evaluations failed to load</h1>
      <p className="mt-2 text-sm">{error.message}</p>
      <button className="mt-4 rounded bg-red-700 px-4 py-2 text-sm font-medium text-white" onClick={reset}>
        Try again
      </button>
    </section>
  );
}
