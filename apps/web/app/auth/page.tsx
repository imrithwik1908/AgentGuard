import Link from "next/link";
import { redirect } from "next/navigation";

import { getSession } from "@/lib/session";

function Field({
  label,
  name,
  type = "text",
  placeholder,
  required = true
}: {
  label: string;
  name: string;
  type?: string;
  placeholder: string;
  required?: boolean;
}) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-slate-600">{label}</span>
      <input
        className="mt-1 w-full rounded-2xl border border-slate-200 bg-white/85 px-4 py-3 text-sm text-ink-950 shadow-sm outline-none transition focus:border-cyan-500 focus:ring-4 focus:ring-cyan-100"
        name={name}
        type={type}
        placeholder={placeholder}
        required={required}
      />
    </label>
  );
}

export default async function AuthPage({
  searchParams
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const session = await getSession();
  if (session) redirect("/");

  const query = await searchParams;
  const mode = query.mode === "login" ? "login" : "register";
  const error = typeof query.error === "string" ? decodeURIComponent(query.error) : "";

  return (
    <div className="mx-auto grid max-w-6xl gap-6 lg:grid-cols-[0.9fr_1.1fr]">
      <section className="relative overflow-hidden rounded-[2rem] bg-ink-950 p-8 text-white shadow-panel">
        <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-cyan-300 via-emerald-300 to-sky-400" />
        <div className="relative space-y-8">
          <Link href="/" className="inline-flex items-center gap-3">
            <span className="grid h-11 w-11 place-items-center rounded-2xl bg-white text-sm font-semibold text-ink-950">
              AG
            </span>
            <span>
              <span className="block text-sm font-semibold">AgentGuard</span>
              <span className="block text-xs text-slate-300">AI reliability control plane</span>
            </span>
          </Link>

          <div>
            <div className="mb-4 inline-flex rounded-full border border-white/10 bg-white/8 px-3 py-1 text-xs text-cyan-100">
              Instrument {"->"} Test {"->"} Evaluate {"->"} Investigate {"->"} Release
            </div>
            <h1 className="max-w-xl text-4xl font-semibold tracking-normal">
              Sign in to your workspace before your AI app starts sending evidence.
            </h1>
            <p className="mt-4 max-w-lg text-sm leading-6 text-slate-300">
              The website is the decision interface. Your SDK/API key is the ingestion credential
              your application uses from an IDE, server, notebook, or CI job.
            </p>
          </div>

          <div className="grid gap-3 text-sm">
            {[
              ["Browser session", "Used by humans to review projects, runs, evaluations, and releases."],
              ["Workspace boundary", "Keeps projects, traces, API keys, and decisions isolated by tenant."],
              ["SDK API key", "Created after login and used by your instrumented AI application."]
            ].map(([title, copy]) => (
              <div key={title} className="rounded-2xl border border-white/10 bg-white/7 p-4">
                <div className="font-medium">{title}</div>
                <div className="mt-1 text-xs leading-5 text-slate-300">{copy}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="surface rounded-[2rem] p-3">
        <div className="grid grid-cols-2 rounded-[1.35rem] bg-slate-100 p-1 text-sm font-medium">
          <Link
            className={`rounded-[1.1rem] px-4 py-3 text-center transition ${
              mode === "register" ? "bg-white text-ink-950 shadow-sm" : "text-slate-600"
            }`}
            href="/auth?mode=register"
          >
            Create workspace
          </Link>
          <Link
            className={`rounded-[1.1rem] px-4 py-3 text-center transition ${
              mode === "login" ? "bg-white text-ink-950 shadow-sm" : "text-slate-600"
            }`}
            href="/auth?mode=login"
          >
            Sign in
          </Link>
        </div>

        <div className="p-6">
          {error ? (
            <div className="mb-5 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
              {error}
            </div>
          ) : null}

          {mode === "login" ? (
            <form action="/auth/login" method="post" className="space-y-4">
              <div>
                <h2 className="text-2xl font-semibold text-ink-950">Welcome back</h2>
                <p className="mt-1 text-sm text-slate-600">
                  Continue to the workspace where your evaluations and traces live.
                </p>
              </div>
              <Field label="Email" name="email" type="email" placeholder="you@example.com" />
              <Field
                label="Workspace slug"
                name="workspace_slug"
                placeholder="research-agent"
                required={false}
              />
              <Field label="Password" name="password" type="password" placeholder="••••••••" />
              <button className="w-full rounded-2xl bg-ink-950 px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:-translate-y-0.5 hover:bg-slate-800">
                Sign in
              </button>
            </form>
          ) : (
            <form action="/auth/register" method="post" className="space-y-4">
              <div>
                <h2 className="text-2xl font-semibold text-ink-950">Create your workspace</h2>
                <p className="mt-1 text-sm text-slate-600">
                  Start with one isolated workspace. You can create SDK API keys after login.
                </p>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <Field label="Your name" name="name" placeholder="Rithwik" />
                <Field label="Email" name="email" type="email" placeholder="you@example.com" />
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <Field label="Workspace name" name="workspace_name" placeholder="Research Agent" />
                <Field label="Workspace slug" name="workspace_slug" placeholder="research-agent" />
              </div>
              <Field label="Password" name="password" type="password" placeholder="At least 8 characters" />
              <button className="w-full rounded-2xl bg-cyan-700 px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:-translate-y-0.5 hover:bg-cyan-800">
                Create workspace
              </button>
            </form>
          )}

          <div className="mt-6 rounded-2xl border border-cyan-100 bg-cyan-50/70 p-4 text-xs leading-5 text-cyan-950">
            Current flow: sign in here, open Setup, create an SDK API key, and copy it into your
            IDE or application runtime. Coming later: a device-flow SDK command that opens the
            browser, waits for login, and returns a scoped key automatically.
          </div>
        </div>
      </section>
    </div>
  );
}
