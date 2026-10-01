"use client";

import { useState, type FormEvent, type ReactNode } from "react";

export function AuthForm({
  action,
  idleLabel,
  pendingLabel,
  tone,
  children
}: {
  action: string;
  idleLabel: string;
  pendingLabel: string;
  tone: "dark" | "cyan";
  children: ReactNode;
}) {
  const [pending, setPending] = useState(false);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    if (pending) {
      event.preventDefault();
      return;
    }
    setPending(true);
  }

  return (
    <form action={action} method="post" className="space-y-4" onSubmit={handleSubmit}>
      {children}
      <button
        aria-busy={pending}
        disabled={pending}
        className={`flex w-full items-center justify-center gap-2 rounded-xl px-5 py-3 text-sm font-semibold text-white transition disabled:cursor-wait disabled:opacity-80 ${
          tone === "cyan" ? "bg-cyan-700 hover:bg-cyan-800" : "bg-ink-950 hover:bg-slate-800"
        }`}
      >
        {pending ? (
          <span aria-hidden="true" className="h-4 w-4 animate-spin rounded-full border-2 border-white/35 border-t-white" />
        ) : null}
        {pending ? pendingLabel : idleLabel}
      </button>
      {pending ? (
        <p className="text-center text-xs text-slate-500" role="status">
          Connecting securely. The first request after inactivity can take a few seconds.
        </p>
      ) : null}
    </form>
  );
}
