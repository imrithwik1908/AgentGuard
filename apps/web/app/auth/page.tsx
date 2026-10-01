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
        className="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3.5 py-3 text-sm text-ink-950 outline-none transition focus:border-cyan-600 focus:ring-4 focus:ring-cyan-100"
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
    <div data-auth-page className="mx-auto grid max-w-4xl gap-10 py-8 lg:grid-cols-[0.85fr_1.15fr] lg:gap-16 lg:py-20">
      <section className="py-4">
        <div className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-700">
          AI application release safety
        </div>
        <h1 className="mt-4 max-w-lg text-3xl font-semibold leading-tight text-ink-950 sm:text-4xl">
          {mode === "login" ? "Return to your evaluation workspace." : "Create your evaluation workspace."}
        </h1>
        <p className="mt-4 max-w-lg text-base leading-7 text-slate-600">
          Compare the same expected behaviors across two application versions, understand what changed, and make a release decision from stored evidence.
        </p>

        <ol className="mt-9 border-y border-slate-200 py-2">
          {[
            ["01", "Instrument", "Record model, retrieval, tool, and workflow steps."],
            ["02", "Evaluate", "Run the same behavioral scenarios against both versions."],
            ["03", "Decide", "Review regressions and the evidence behind the release signal."]
          ].map(([number, title, description]) => (
            <li key={number} className="grid grid-cols-[2.5rem_6rem_1fr] gap-2 border-b border-slate-100 py-3 text-sm last:border-0">
              <span className="font-mono text-xs text-cyan-700">{number}</span>
              <span className="font-semibold text-ink-950">{title}</span>
              <span className="leading-5 text-slate-600">{description}</span>
            </li>
          ))}
        </ol>
      </section>

      <section className="border-t border-slate-200 pt-7 lg:border-l lg:border-t-0 lg:pl-14 lg:pt-2">
        <div className="grid grid-cols-2 border-b border-slate-200 text-sm font-medium">
          <Link
            className={`border-b-2 px-4 py-3 text-center transition ${
              mode === "register" ? "border-cyan-600 text-ink-950" : "border-transparent text-slate-500 hover:text-ink-950"
            }`}
            href="/auth?mode=register"
          >
            Create workspace
          </Link>
          <Link
            className={`border-b-2 px-4 py-3 text-center transition ${
              mode === "login" ? "border-cyan-600 text-ink-950" : "border-transparent text-slate-500 hover:text-ink-950"
            }`}
            href="/auth?mode=login"
          >
            Sign in
          </Link>
        </div>

        <div className="pt-8">
          {error ? (
            <div className="mb-5 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
              {error}
            </div>
          ) : null}

          {mode === "login" ? (
            <AuthForm action="/auth/login" idleLabel="Sign in" pendingLabel="Signing in..." tone="dark">
              <div>
                <h2 className="text-2xl font-semibold text-ink-950">Sign in</h2>
                <p className="mt-1 text-sm text-slate-600">
                  Open the workspace where your projects, test suites, and release evidence live.
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
