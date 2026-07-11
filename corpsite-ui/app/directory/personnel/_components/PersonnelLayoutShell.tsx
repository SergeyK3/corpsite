"use client";

import type { ReactNode } from "react";
import { usePathname } from "next/navigation";

import { isPersonnelOrderPrintRoute } from "../_lib/personnelOrderPrintLanguage";
import PersonnelSectionHeader from "./PersonnelSectionHeader";

export default function PersonnelLayoutShell({ children }: { children: ReactNode }) {
  const pathname = usePathname() || "";
  const isImportCardPage = /\/directory\/personnel\/employees\/[^/]+\/import-card(?:\/|$)/.test(pathname);
  const isPrintPage = isPersonnelOrderPrintRoute(pathname);
  const barePage = isImportCardPage || isPrintPage;

  if (isPrintPage) {
    return <div className="min-h-0 min-w-0">{children}</div>;
  }

  return (
    <div className="mx-auto w-full max-w-[1440px] px-4 py-3">
      <div className="rounded-2xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
        {!barePage ? (
          <div className="border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
            <PersonnelSectionHeader />
          </div>
        ) : null}
        <div className={barePage ? "min-h-0 min-w-0" : "min-w-0"}>{children}</div>
      </div>
    </div>
  );
}
