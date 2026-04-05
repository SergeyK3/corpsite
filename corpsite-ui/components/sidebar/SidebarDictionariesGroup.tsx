// FILE: corpsite-ui/components/sidebar/SidebarDictionariesGroup.tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import * as React from "react";
import { DICTIONARIES } from "../../app/directory/_lib/dictionaries.config";

function isPathActive(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export default function SidebarDictionariesGroup() {
  const pathname = usePathname();
  const sectionActive = isPathActive(pathname, "/admin/dictionaries");

  const [open, setOpen] = React.useState(sectionActive);

  React.useEffect(() => {
    if (sectionActive) setOpen(true);
  }, [sectionActive]);

  return (
    <div className="space-y-1">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className={`flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-sm transition ${
          sectionActive
            ? "bg-zinc-200 text-zinc-900"
            : "text-zinc-700 hover:bg-zinc-200 hover:text-zinc-900"
        }`}
      >
        <span className="font-medium">Справочники</span>
        <span className={`text-xs text-zinc-600 transition ${open ? "rotate-180" : ""}`}>▾</span>
      </button>

      {open ? (
        <div className="ml-3 space-y-1 border-l border-zinc-200 pl-3">
          <Link
            href="/admin/dictionaries"
            className={`block rounded-lg px-3 py-2 text-sm transition ${
              pathname === "/admin/dictionaries"
                ? "bg-zinc-200 text-zinc-900"
                : "text-zinc-600 hover:bg-zinc-200 hover:text-zinc-900"
            }`}
          >
            Обзор
          </Link>

          {DICTIONARIES.map((item) => {
            const href = `/admin/dictionaries/${item.code}`;
            const active = isPathActive(pathname, href);

            return (
              <Link
                key={item.code}
                href={href}
                className={`block rounded-lg px-3 py-2 text-sm transition ${
                  active
                    ? "bg-zinc-200 text-zinc-900"
                    : "text-zinc-600 hover:bg-zinc-200 hover:text-zinc-900"
                }`}
              >
                {item.title}
              </Link>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}