"use client";

import * as React from "react";

import PositionsPageClient from "./PositionsPageClient";
import PositionAssignmentReport from "./PositionAssignmentReport";

export default function PositionsTabsPageClient() {
  const [tab, setTab] = React.useState<"catalog" | "reports">("catalog");

  return (
    <div>
      <div className="mx-auto max-w-[1440px] px-4 pt-3">
        <div role="tablist" aria-label="Разделы страницы Должности" className="flex gap-1 border-b border-zinc-200 dark:border-zinc-800">
          <button type="button" role="tab" aria-selected={tab === "catalog"} aria-controls="positions-catalog-panel"
            onClick={() => setTab("catalog")}
            className={`rounded-t-lg px-4 py-2 text-sm font-medium ${tab === "catalog" ? "border border-b-0 border-zinc-200 bg-white text-zinc-900 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-50" : "text-zinc-600 hover:text-zinc-900 dark:text-zinc-400"}`}>
            Справочник
          </button>
          <button type="button" role="tab" aria-selected={tab === "reports"} aria-controls="positions-reports-panel"
            onClick={() => setTab("reports")}
            className={`rounded-t-lg px-4 py-2 text-sm font-medium ${tab === "reports" ? "border border-b-0 border-zinc-200 bg-white text-zinc-900 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-50" : "text-zinc-600 hover:text-zinc-900 dark:text-zinc-400"}`}>
            Отчёты
          </button>
        </div>
      </div>
      <div id="positions-catalog-panel" role="tabpanel" hidden={tab !== "catalog"}>
        <PositionsPageClient />
      </div>
      {tab === "reports" ? (
        <div id="positions-reports-panel" role="tabpanel">
          <PositionAssignmentReport />
        </div>
      ) : null}
    </div>
  );
}
