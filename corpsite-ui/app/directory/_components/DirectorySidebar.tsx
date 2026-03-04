// FILE: corpsite-ui/app/directory/_components/DirectorySidebar.tsx
"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

type NavItem = { href: string; label: string };

const NAV: NavItem[] = [
  { href: "/tasks", label: "Задачи" },
  { href: "/directory/org", label: "Оргструктура" },
  { href: "/directory/employees", label: "Сотрудники" },
];

export default function DirectorySidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-[360px] shrink-0 px-4 py-8">
      <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4">
        <div className="space-y-3">
          {NAV.map((item) => {
            const active =
              pathname === item.href || (item.href !== "/" && pathname?.startsWith(item.href + "/"));

            return (
              <Link
                key={item.href}
                href={item.href}
                className={[
                  "block rounded-lg border px-4 py-3 text-left text-sm",
                  "border-zinc-800 bg-zinc-950/40 text-zinc-100 hover:bg-zinc-900/60",
                  active ? "outline outline-1 outline-zinc-600" : "",
                ].join(" ")}
              >
                {item.label}
              </Link>
            );
          })}
        </div>
      </div>
    </aside>
  );
}