import type { Metadata } from "next";
import Link from "next/link";

import { logoutAction } from "./auth/actions";
import "./globals.css";
import { getSession } from "@/lib/session";

export const metadata: Metadata = {
  title: "AgentGuard",
  description: "Reliability control plane for LLM, RAG, and agentic applications"
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const session = await getSession();

  return (
    <html lang="en">
      <body>
        <div className="min-h-screen">
          <header className="sticky top-0 z-10 border-b border-slate-200/70 bg-white/82 backdrop-blur-xl">
            <div className="mx-auto flex max-w-7xl flex-col gap-3 px-5 py-3 lg:flex-row lg:items-center lg:justify-between">
              <Link href="/" className="flex items-center gap-3">
                <div className="grid h-10 w-10 place-items-center rounded-xl bg-ink-900 text-sm font-semibold text-white shadow-sm">
                  AG
                </div>
                <div>
                  <div className="text-sm font-semibold tracking-wide text-ink-950">AgentGuard</div>
                  <div className="text-xs text-slate-500">AI reliability control plane</div>
                </div>
              </Link>
              <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
                <nav className="flex w-full items-center gap-1 overflow-x-auto rounded-full border border-slate-200 bg-white/72 p-1 text-sm shadow-sm lg:w-auto">
                  <Link className="rounded-full px-3 py-2 text-slate-700 hover:bg-slate-100" href="/">
                    Overview
                  </Link>
                  <Link className="rounded-full px-3 py-2 text-slate-700 hover:bg-slate-100" href="/datasets">
                    Test Suites
                  </Link>
                  <Link className="rounded-full px-3 py-2 text-slate-700 hover:bg-slate-100" href="/releases">
                    Releases
                  </Link>
                  <Link className="rounded-full px-3 py-2 text-slate-700 hover:bg-slate-100" href="/traces">
                    Runs
                  </Link>
                  <Link className="rounded-full px-3 py-2 text-slate-700 hover:bg-slate-100" href="/projects">
                    Setup
                  </Link>
                  <Link className="rounded-full px-3 py-2 text-slate-700 hover:bg-slate-100" href="/docs">
                    Docs
                  </Link>
                </nav>
                {session ? (
                  <div className="flex items-center gap-2 rounded-full border border-slate-200 bg-white/80 p-1 pl-3 text-xs shadow-sm">
                    <div>
                      <div className="font-medium text-ink-950">{session.workspace.name}</div>
                      <div className="text-slate-500">{session.user.email}</div>
                    </div>
                    <form action={logoutAction}>
                      <button className="rounded-full bg-slate-100 px-3 py-2 font-medium text-slate-700 transition hover:bg-slate-200">
                        Logout
                      </button>
                    </form>
                  </div>
                ) : (
                  <Link
                    href="/auth"
                    className="rounded-full bg-ink-950 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800"
                  >
                    Sign in
                  </Link>
                )}
              </div>
            </div>
          </header>
          <main className="mx-auto max-w-7xl px-6 py-7 reveal">{children}</main>
        </div>
      </body>
    </html>
  );
}
