"use client";

import type { ReactNode } from "react";
import { usePathname } from "next/navigation";

import PersonnelSectionHeader from "./PersonnelSectionHeader";

export default function PersonnelLayoutShell({ children }: { children: ReactNode }) {
  const pathname = usePathname() || "";
  const isImportCardPage = /\/directory\/personnel\/employees\/[^/]+\/import-card(?:\/|$)/.test(pathname);

  return (
    <>
      {!isImportCardPage ? (
        <div className="border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
          <PersonnelSectionHeader />
        </div>
      ) : null}
      <div className={isImportCardPage ? "min-h-0 min-w-0" : "min-w-0"}>{children}</div>
    </>
  );
}
