import Link from "next/link";

import { ApiUnavailable } from "@/components/api-unavailable";
import { ApiKeyCreator } from "@/components/api-key-creator";
import { getEvaluationCapabilities, listApiKeys, listProviders, listRedactionPolicies, listWorkspaces } from "@/lib/api";
import { formatDateTime } from "@/lib/format";

export default async function SettingsPage() {
  let workspaces;
  let apiKeys;
  let providers;
  let policies;
  let capabilities;
  try {
    [workspaces, apiKeys, providers, policies, capabilities] = await Promise.all([
      listWorkspaces(),
      listApiKeys(),
      listProviders(),
      listRedactionPolicies(),
      getEvaluationCapabilities()
    ]);
  } catch (error) {
    return (
      <ApiUnavailable
        title="Settings cannot reach the AgentGuard API"
        detail={error instanceof Error ? error.message : String(error)}
      />
    );
  }

  return (
    <div className="space-y-8">
      <section className="surface rounded-[2rem] p-6">
        <div className="text-xs font-medium uppercase tracking-[0.22em] text-cyan-700">
          Connect your application
        </div>
        <h1 className="mt-3 text-3xl font-semibold text-ink-950">Setup</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
          Create the credentials your SDK uses, confirm workspace isolation, then register projects
          and versions before running evaluations. Browser login is for humans; SDK API keys are for
          your instrumented AI application.
        </p>
        <div className="mt-5 flex flex-wrap gap-3">
          <Link
            className="rounded-full bg-ink-950 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800"
            href="/projects"
          >
            Register projects and versions
          </Link>
          <Link
            className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
            href="/docs"
          >
            SDK quickstart
          </Link>
        </div>
      </section>

      <section className="flex flex-wrap items-center justify-between gap-4 border-y border-slate-200 py-4">
        <div>
          <div className="text-sm font-semibold text-ink-950">Evaluation engine</div>
          <p className="mt-1 text-sm text-slate-600">
            {capabilities.ai_judges_enabled
              ? `Semantic judging is active with ${capabilities.judge_model}.`
              : "Deterministic checks are active. No semantic judge is connected."}
          </p>
        </div>
        <div className="text-sm text-slate-500">
          {apiKeys.length} SDK key{apiKeys.length === 1 ? "" : "s"} · {workspaces.length} workspace{workspaces.length === 1 ? "" : "s"}
        </div>
      </section>

      <ApiKeyCreator workspaces={workspaces} apiKeys={apiKeys} />

      <section className="grid gap-5 lg:grid-cols-3">
        <Panel title="Workspaces">
          {workspaces.map((workspace) => (
            <Row
              key={workspace.id}
              title={workspace.name}
              meta={`${workspace.slug} · ${formatDateTime(workspace.created_at)}`}
            />
          ))}
        </Panel>
        <Panel title="Provider integrations">
          {providers.map((provider) => (
            <Row
              key={provider.id}
              title={`${provider.provider} / ${provider.name}`}
              meta={`${provider.default_model ?? "model unset"} · ${provider.is_enabled ? "enabled" : "disabled"}`}
            />
          ))}
        </Panel>
        <Panel title="Redaction policies">
          {policies.map((policy) => (
            <Row
              key={policy.id}
              title={policy.name}
              meta={`${policy.mode} · ${policy.is_enabled ? "enabled" : "disabled"}`}
            />
          ))}
        </Panel>
      </section>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="surface rounded-[2rem] p-5">
      <h2 className="text-sm font-semibold text-ink-950">{title}</h2>
      <div className="mt-4 space-y-3">
        {children || <div className="text-sm text-slate-500">Nothing configured yet.</div>}
      </div>
    </div>
  );
}

function Row({ title, meta }: { title: string; meta: string }) {
  return (
    <div className="rounded-2xl bg-slate-50/90 p-3">
      <div className="font-medium text-ink-950">{title}</div>
      <div className="mt-1 text-xs text-slate-500">{meta}</div>
    </div>
  );
}
