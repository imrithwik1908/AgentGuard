import Link from "next/link";

import { getApiUrl } from "@/lib/api";

export function ApiUnavailable({
  title = "AgentGuard API is not reachable",
  detail
}: {
  title?: string;
  detail?: string;
}) {
  return (
    <section className="rounded border border-amber-200 bg-amber-50 p-6 shadow-panel">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="max-w-3xl">
          <h1 className="text-lg font-semibold text-amber-950">{title}</h1>
          <p className="mt-2 text-sm leading-6 text-amber-900">
            The web UI is running, but it cannot load telemetry because the backend API did not
            respond at <code className="rounded bg-amber-100 px-1 py-0.5">{getApiUrl()}</code>.
          </p>
          <div className="mt-4 rounded border border-amber-200 bg-white/70 p-3">
            <div className="text-xs font-medium uppercase tracking-wide text-amber-700">
              Start the local backend
            </div>
            <pre className="mt-2 text-xs leading-5 text-amber-950">
              {`docker compose up --build

# or run API + Postgres locally, then refresh this page`}
            </pre>
          </div>
          {detail ? (
            <details className="mt-4">
              <summary className="cursor-pointer text-sm font-medium text-amber-900">
                Technical details
              </summary>
              <pre className="mt-2 rounded bg-amber-100 p-3 text-xs text-amber-950">
                {detail}
              </pre>
            </details>
          ) : null}
        </div>
        <Link
          href="/projects"
          className="inline-flex rounded bg-amber-900 px-4 py-2 text-sm font-medium text-white hover:bg-amber-800"
        >
          Retry
        </Link>
      </div>
    </section>
  );
}
