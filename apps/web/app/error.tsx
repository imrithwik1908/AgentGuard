"use client";

export default function ErrorPage({
  error,
  reset
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="rounded border border-red-200 bg-red-50 p-6">
      <h1 className="text-lg font-semibold text-red-900">AgentGuard UI could not load this view</h1>
      <p className="mt-2 text-sm text-red-800">{error.message}</p>
      <button
        type="button"
        onClick={reset}
        className="mt-4 rounded bg-red-700 px-4 py-2 text-sm font-medium text-white hover:bg-red-800"
      >
        Retry
      </button>
    </div>
  );
}

