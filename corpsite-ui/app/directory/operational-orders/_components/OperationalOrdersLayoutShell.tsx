"use client";

import type { ReactNode } from "react";

import OperationalOrdersSectionHeader from "./OperationalOrdersSectionHeader";

export default function OperationalOrdersLayoutShell({ children }: { children: ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-[1440px] px-4 py-3">
      <div className="rounded-2xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
        <div className="border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
          <OperationalOrdersSectionHeader />
        </div>
        <div className="min-w-0 p-4">{children}</div>
      </div>
    </div>
  );
}
