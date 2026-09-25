import Link from "next/link";

import { logoutAction } from "@/app/auth/actions";
import { RetryButton } from "@/components/retry-button";

export function ApiUnavailable({
  title = "AgentGuard is waking up",
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
    <section className="overflow-hidden rounded-2xl border border-amber-200 bg-white shadow-panel">
      <div className="h-1 bg-amber-400" />
      <div className="p-6 sm:p-8">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="max-w-3xl">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-amber-700">
            Connection status
          </p>
          <h1 className="mt-2 text-xl font-semibold text-slate-950">{displayTitle}</h1>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            {authenticationRequired ? (
              "Your saved session is no longer accepted by the API. Sign in again to continue."
            ) : (
              "The dashboard is online. Its free demo API may need up to a minute to resume after a period of inactivity. Your data is not affected."
            )}
          </p>
          {detail ? (
            <details className="mt-4">
              <summary className="cursor-pointer text-sm font-medium text-slate-600">
                Technical details
              </summary>
              <pre className="mt-2 max-w-full overflow-x-auto rounded-lg bg-slate-100 p-3 text-xs text-slate-700">
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
          <RetryButton />
        )}
      </div>
      </div>
    </section>
  );
}
