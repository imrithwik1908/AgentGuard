"use client";

export default function SettingsError({ error }: { error: Error }) {
  return (
    <section className="rounded-[2rem] border border-amber-200 bg-amber-50 p-6 shadow-panel">
      <h1 className="text-lg font-semibold text-amber-950">Settings could not load</h1>
      <pre className="mt-4 rounded bg-amber-100 p-3 text-xs text-amber-950">{error.message}</pre>
    </section>
  );
}
