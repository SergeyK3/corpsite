// PMF-4B.1 — "What to do next" block on Migration Home.
"use client";

import { MIGRATION_NEXT_STEPS } from "../_lib/personnelMigrationHrLabels";

export default function MigrationNextSteps() {
  return (
    <section
      aria-label="Что делать дальше"
      className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950"
    >
      <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Что делать дальше?</h2>
      <ol className="mt-4 space-y-4">
        {MIGRATION_NEXT_STEPS.map((step) => (
          <li key={step.number} className="flex gap-3">
            <span
              className={[
                "flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
                step.available
                  ? "bg-blue-600 text-white"
                  : "bg-zinc-100 text-zinc-500 dark:bg-zinc-900 dark:text-zinc-400",
              ].join(" ")}
            >
              {step.number}
            </span>
            <div className="min-w-0">
              <p
                className={[
                  "text-sm font-medium",
                  step.available ? "text-zinc-900 dark:text-zinc-100" : "text-zinc-600 dark:text-zinc-400",
                ].join(" ")}
              >
                {step.title}
              </p>
              <p className="mt-0.5 text-sm text-zinc-500">{step.description}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
