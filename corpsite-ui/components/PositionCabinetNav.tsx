// FILE: corpsite-ui/components/PositionCabinetNav.tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  getPositionCabinetTabLabel,
  POSITION_CABINET_NAV_ITEMS,
  resolvePositionCabinetSection,
} from "@/lib/positionCabinetNav";

function tabClassName(active: boolean): string {
  return [
    "inline-flex items-center rounded-md px-3 py-2 text-sm font-medium transition",
    active
      ? "bg-zinc-200 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-50"
      : "text-zinc-800 dark:text-zinc-200 hover:bg-zinc-200 dark:hover:bg-zinc-700",
  ].join(" ");
}

export default function PositionCabinetNav() {
  const pathname = usePathname() || "/tasks";
  const activeSection = resolvePositionCabinetSection(pathname);

  return (
    <div
      className="flex flex-wrap items-center gap-1 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 p-1"
      role="tablist"
      aria-label="Разделы личного кабинета должности"
      data-testid="position-cabinet-nav"
    >
      {POSITION_CABINET_NAV_ITEMS.map((item) => {
        const label = getPositionCabinetTabLabel(item.id);
        const active = activeSection === item.id;

        return (
          <Link
            key={item.id}
            href={item.href}
            className={tabClassName(active)}
            aria-current={active ? "page" : undefined}
            role="tab"
            aria-selected={active}
            data-testid={`position-cabinet-tab-${item.id}`}
          >
            <span className="whitespace-nowrap">{label}</span>
          </Link>
        );
      })}
    </div>
  );
}
