import Link from "next/link";

import { logoutAction } from "@/app/auth/actions";
import { getApiUrl } from "@/lib/api";

export function ApiUnavailable({
  title = "AgentGuard API is not reachable",
  detail
}: {
  title?: string;
  detail?: string;
}) {
  const authenticationRequired = Boolean(
    detail && /auth|session|token|401|credential/i.test(detail)
  );
  const displayTitle = authenticationRequired ? "Sign in again" : title;
  return (
    <section className="rounded border border-amber-200 bg-amber-50 p-6 shadow-panel">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="max-w-3xl">
          <h1 className="text-lg font-semibold text-amber-950">{displayTitle}</h1>
          <p className="mt-2 text-sm leading-6 text-amber-900">
            {authenticationRequired ? (
              "Your saved session is no longer accepted by the API. Sign in again to continue."
            ) : (
              <>
                The web UI is running, but the backend did not respond at{" "}
                <code className="rounded bg-amber-100 px-1 py-0.5">{getApiUrl()}</code>.
              </>
            )}
          </p>
          {!authenticationRequired ? (
            <div className="mt-4 rounded border border-amber-200 bg-white/70 p-3">
              <div className="text-xs font-medium uppercase tracking-wide text-amber-700">
                Start the local backend
              </div>
              <pre className="mt-2 text-xs leading-5 text-amber-950">
                {`docker compose up --build

# or run API + Postgres locally, then refresh this page`}
              </pre>
            </div>
          ) : null}
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
        {authenticationRequired ? (
          <form action={logoutAction}>
            <button className="inline-flex rounded bg-amber-900 px-4 py-2 text-sm font-medium text-white hover:bg-amber-800">
              Sign in again
            </button>
          </form>
        ) : (
          <Link
            href="/projects"
            className="inline-flex rounded bg-amber-900 px-4 py-2 text-sm font-medium text-white hover:bg-amber-800"
          >
            Retry
          </Link>
        )}
      </div>
    </section>
  );
}
