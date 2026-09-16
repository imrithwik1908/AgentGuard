import { ApiUnavailable } from "@/components/api-unavailable";
import { MetricCard } from "@/components/metric-card";
import { listProviders, listRedactionPolicies, listWorkspaces } from "@/lib/api";
import { formatDateTime } from "@/lib/format";

export default async function SettingsPage() {
  let workspaces;
  let providers;
  let policies;
  try {
    [workspaces, providers, policies] = await Promise.all([
      listWorkspaces(),
      listProviders(),
      listRedactionPolicies()
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
          Production controls
        </div>
        <h1 className="mt-3 text-3xl font-semibold text-ink-950">Settings</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
          Manage the platform layer around tracing and evaluations: workspaces, API access,
          provider configuration, and redaction rules. Auth enforcement is enabled in production
          with <code className="rounded bg-slate-100 px-1">AGENTGUARD_AUTH_REQUIRED=true</code>.
        </p>
      </section>

      <section className="flex flex-col gap-3 rounded-[1.5rem] border border-slate-200/80 bg-white/70 p-3 shadow-panel backdrop-blur md:flex-row">
        <MetricCard label="Workspaces" value={workspaces.length} detail="Tenant boundaries" tone="focus" />
        <MetricCard label="Providers" value={providers.length} detail="External LLM configs" />
        <MetricCard label="Policies" value={policies.length} detail="Redaction controls" />
      </section>

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
