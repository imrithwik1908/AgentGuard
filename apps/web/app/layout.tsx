import type { Metadata } from "next";
import Link from "next/link";

import { ProductNavigation } from "@/components/product-navigation";
import { logoutAction } from "./auth/actions";
import "./globals.css";
import { getSession } from "@/lib/session";

export const metadata: Metadata = {
  title: "AgentGuard",
  description: "Reliability control plane for LLM, RAG, and agentic applications"
};

export const maxDuration = 60;

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const session = await getSession();

  return (
    <html lang="en">
      <body>
        <div className="min-h-screen">
          <header className="sticky top-0 z-20 border-b border-slate-200/70 bg-white/90 backdrop-blur-xl">
            <div className="mx-auto flex max-w-[1180px] flex-col gap-3 px-5 py-3 lg:flex-row lg:items-center lg:justify-between">
              <Link href="/" className="flex items-center gap-3">
                <div className="grid h-9 w-9 place-items-center rounded-lg bg-ink-950 text-xs font-semibold text-white shadow-sm">
                  AG
                </div>
                <div>
                  <div className="text-sm font-semibold tracking-wide text-ink-950">AgentGuard</div>
                  <div className="text-xs text-slate-500">AI reliability control plane</div>
                </div>
              </Link>
              <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:gap-5">
                <ProductNavigation />
                {session ? (
                  <div className="flex items-center gap-3 border-l border-slate-200 pl-4 text-xs">
                    <div>
                      <div className="font-medium text-ink-950">{session.workspace.name}</div>
                      <div className="text-slate-500">{session.user.email}</div>
                    </div>
                    <form action={logoutAction}>
                      <button className="rounded-lg bg-slate-100 px-3 py-2 font-medium text-slate-700 transition hover:bg-slate-200">
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
          <main className="mx-auto max-w-[1180px] px-5 py-9 sm:px-7 lg:py-12 reveal">{children}</main>
        </div>
      </body>
    </html>
  );
}
