// PMF-4B.1 — planned HR data types roadmap.
"use client";

import { MIGRATION_ROADMAP_ITEMS } from "../_lib/personnelMigrationHrLabels";
import { HR_DOSSIER_GENITIVE } from "@/lib/personnelCardTerminology";

function roadmapMarker(status: (typeof MIGRATION_ROADMAP_ITEMS)[number]["status"]): string {
  switch (status) {
    case "current":
      return "✓";
    case "available":
      return "✓";
    default:
      return "○";
  }
}

function roadmapLabelClass(status: (typeof MIGRATION_ROADMAP_ITEMS)[number]["status"]): string {
  return status === "planned"
    ? "text-zinc-500 dark:text-zinc-400"
    : "font-medium text-zinc-900 dark:text-zinc-100";
}

export default function MigrationRoadmapPanel() {
  return (
    <section
      aria-label="План развития"
      className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950"
    >
      <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Будут доступны</h2>
      <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
        Инструмент переноса данных будет расширяться на все основные разделы {HR_DOSSIER_GENITIVE}.
      </p>
      <ul className="mt-4 grid gap-2 sm:grid-cols-2">
        {MIGRATION_ROADMAP_ITEMS.map((item) => (
          <li key={item.label} className="flex items-center gap-2 text-sm">
            <span
              aria-hidden="true"
              className={[
                "w-4 shrink-0 text-center font-mono text-xs",
                item.status === "current" ? "text-emerald-600 dark:text-emerald-400" : "text-zinc-400",
              ].join(" ")}
            >
              {roadmapMarker(item.status)}
            </span>
            <span className={roadmapLabelClass(item.status)}>{item.label}</span>
            {item.status === "current" ? (
              <span className="text-[11px] text-zinc-500">— сейчас</span>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
