"use client";

export default function DatasetsError({ error }: { error: Error }) {
  return (
    <section className="rounded border border-amber-200 bg-amber-50 p-6 shadow-panel">
      <h1 className="text-lg font-semibold text-amber-950">Datasets could not load</h1>
      <p className="mt-2 text-sm leading-6 text-amber-900">
        The datasets page hit an unexpected rendering error. Refresh after confirming the API is
        running.
      </p>
      <pre className="mt-4 rounded bg-amber-100 p-3 text-xs text-amber-950">{error.message}</pre>
    </section>
  );
}
