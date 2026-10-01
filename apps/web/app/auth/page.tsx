import Link from "next/link";
import { redirect } from "next/navigation";

import { AuthForm } from "@/components/auth-form";
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
    <div className="mx-auto grid max-w-5xl gap-12 py-6 lg:grid-cols-[0.9fr_1.1fr] lg:items-center lg:py-14">
      <section className="py-6">
        <div className="space-y-9">
          <Link href="/" className="inline-flex items-center gap-3">
            <span className="grid h-11 w-11 place-items-center rounded-xl bg-ink-950 text-sm font-semibold text-white">
              AG
            </span>
            <span>
              <span className="block text-sm font-semibold text-ink-950">AgentGuard</span>
              <span className="block text-xs text-slate-500">AI reliability control plane</span>
            </span>
          </Link>

          <div>
            <div className="mb-4 text-xs font-semibold uppercase tracking-[0.18em] text-cyan-700">
              Instrument {"->"} Test {"->"} Evaluate {"->"} Investigate {"->"} Release
            </div>
            <h1 className="max-w-xl text-4xl font-semibold leading-tight tracking-normal text-ink-950">
              Understand whether an AI application change is safe to ship.
            </h1>
            <p className="mt-4 max-w-lg text-base leading-7 text-slate-600">
              Connect an application, rerun expected behaviors against two versions, and investigate what became better or worse.
            </p>
          </div>

          <div className="border-y border-slate-200 py-5 text-sm leading-6 text-slate-600">
            <p><strong className="text-ink-950">Connect your app.</strong> The SDK records complete runs and important internal steps.</p>
            <p className="mt-3"><strong className="text-ink-950">Test a change.</strong> The same scenarios run against a baseline and candidate.</p>
            <p className="mt-3"><strong className="text-ink-950">Decide with evidence.</strong> AgentGuard separates execution failures from behavioral regressions.</p>
          </div>
        </div>
      </section>

      <section className="data-surface p-3">
        <div className="grid grid-cols-2 rounded-xl bg-slate-100 p-1 text-sm font-medium">
          <Link
            className={`rounded-lg px-4 py-3 text-center transition ${
              mode === "register" ? "rounded-lg bg-white text-ink-950 shadow-sm" : "rounded-lg text-slate-600"
            }`}
            href="/auth?mode=register"
          >
            Create workspace
          </Link>
          <Link
            className={`rounded-lg px-4 py-3 text-center transition ${
              mode === "login" ? "rounded-lg bg-white text-ink-950 shadow-sm" : "rounded-lg text-slate-600"
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
            <AuthForm action="/auth/login" idleLabel="Sign in" pendingLabel="Signing in..." tone="dark">
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
            </AuthForm>
          ) : (
            <AuthForm action="/auth/register" idleLabel="Create workspace" pendingLabel="Creating workspace..." tone="cyan">
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
            </AuthForm>
          )}
        </div>
      </section>
    </div>
  );
}
