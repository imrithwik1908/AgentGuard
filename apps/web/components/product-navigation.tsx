"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const items = [
  ["Overview", "/"],
  ["Test Suites", "/datasets"],
  ["Releases", "/releases"],
  ["Runs", "/traces"],
  ["Setup", "/settings"],
  ["Docs", "/docs"]
] as const;

export function ProductNavigation() {
  const pathname = usePathname();
  return (
    <nav aria-label="Primary navigation" className="flex items-center gap-1 overflow-x-auto">
      {items.map(([label, href]) => {
        const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={`relative shrink-0 px-3 py-2 text-sm font-medium transition-colors after:absolute after:inset-x-3 after:-bottom-[13px] after:h-0.5 after:rounded-full after:transition-colors ${
              active
                ? "text-ink-950 after:bg-cyan-600"
                : "text-slate-500 after:bg-transparent hover:text-ink-950"
            }`}
          >
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
