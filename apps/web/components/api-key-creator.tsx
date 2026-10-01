"use client";

import { useActionState, useRef, useState } from "react";

import { createApiKeyAction, type CreateApiKeyState } from "@/app/settings/actions";
import type { ApiKey, Workspace } from "@/lib/types";

const initialState: CreateApiKeyState = { status: "idle" };

export function ApiKeyCreator({
  workspaces,
  apiKeys
}: {
  workspaces: Workspace[];
  apiKeys: ApiKey[];
}) {
  const [state, formAction, pending] = useActionState(createApiKeyAction, initialState);
  const [copied, setCopied] = useState(false);
  const keyRef = useRef<HTMLInputElement>(null);

  async function copyKey() {
    if (!state.apiKey) return;
    await navigator.clipboard.writeText(state.apiKey);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1800);
  }

  return (
    <section className="tool-panel overflow-hidden">
      <div>
        <div className="border-b border-slate-200/80 p-5 sm:px-7">
          <div className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-700">
            SDK access
          </div>
          <h2 className="mt-2 text-xl font-semibold text-ink-950">Create an API key</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            Use this key from your IDE, notebook, server, or CI job so the AgentGuard SDK can
            submit runs for this workspace.
          </p>
        </div>

        <div className="p-5 sm:px-7">
          <form action={formAction} className="grid gap-4 md:grid-cols-[1fr_1fr_auto] md:items-end">
            <label className="block">
              <span className="text-xs font-medium text-slate-600">Workspace</span>
              <select
                className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-ink-950 outline-none transition focus:border-cyan-500 focus:ring-4 focus:ring-cyan-100"
                name="workspace_id"
                required
              >
                {workspaces.map((workspace) => (
                  <option key={workspace.id} value={workspace.id}>
                    {workspace.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="text-xs font-medium text-slate-600">Key name</span>
              <input
                className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-ink-950 outline-none transition focus:border-cyan-500 focus:ring-4 focus:ring-cyan-100"
                name="name"
                placeholder="Local IDE, staging app, CI runner"
                required
              />
            </label>
            <button
              className="rounded-lg bg-ink-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={pending || workspaces.length === 0}
            >
              {pending ? "Creating..." : "Create key"}
            </button>
          </form>

          {state.status !== "idle" ? (
            <div
              className={`mt-5 rounded-lg border p-4 text-sm ${
                state.status === "created"
                  ? "border-emerald-200 bg-emerald-50 text-emerald-950"
                  : "border-red-200 bg-red-50 text-red-950"
              }`}
            >
              <div className="font-medium">{state.message}</div>
              {state.apiKey ? (
                <div className="mt-3 flex flex-col gap-2 md:flex-row">
                  <input
                    ref={keyRef}
                    className="min-w-0 flex-1 rounded-lg border border-emerald-200 bg-white px-3 py-2 font-mono text-xs text-ink-950"
                    readOnly
                    value={state.apiKey}
                    onFocus={() => keyRef.current?.select()}
                  />
                  <button
                    className="rounded-lg bg-emerald-700 px-4 py-2 text-xs font-semibold text-white transition hover:bg-emerald-800"
                    type="button"
                    onClick={copyKey}
                  >
                    {copied ? "Copied" : "Copy key"}
                  </button>
                </div>
              ) : null}
            </div>
          ) : null}

          <div className="mt-6">
            <div className="mb-3 flex items-center justify-between gap-3">
              <h3 className="text-sm font-semibold text-ink-950">Existing keys</h3>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">
                {apiKeys.length} total
              </span>
            </div>
            <div className="divide-y divide-slate-100 border-t border-slate-200">
              {apiKeys.length === 0 ? (
                <div className="p-4 text-sm text-slate-500">
                  No SDK keys yet. Create one when you are ready to connect an application.
                </div>
              ) : (
                apiKeys.map((key) => (
                  <div key={key.id} className="grid gap-2 p-4 md:grid-cols-[1fr_auto] md:items-center">
                    <div>
                      <div className="font-medium text-ink-950">{key.name}</div>
                      <div className="mt-1 font-mono text-xs text-slate-500">
                        Prefix {key.prefix}... · {key.is_active ? "active" : "inactive"}
                      </div>
                    </div>
                    <div className="text-xs text-slate-500">
                      {key.last_used_at ? `Last used ${new Date(key.last_used_at).toLocaleString()}` : "Never used"}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
