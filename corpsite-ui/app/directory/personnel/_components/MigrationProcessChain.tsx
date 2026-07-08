// PMF-4B.1 — visual HR process chain on Migration Home.
"use client";

import Link from "next/link";
import * as React from "react";

import {
  MIGRATION_CURRENT_STEP_ID,
  MIGRATION_PROCESS_STEPS,
} from "../_lib/personnelMigrationHrLabels";

function stepShellClass(active: boolean): string {
  return [
    "flex flex-1 flex-col items-center rounded-lg border px-3 py-3 text-center transition",
    active
      ? "border-blue-300 bg-blue-50 dark:border-blue-800 dark:bg-blue-950/50"
      : "border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950",
  ].join(" ");
}

function stepTitleClass(active: boolean): string {
  return active
    ? "text-sm font-semibold text-blue-900 dark:text-blue-100"
    : "text-sm font-medium text-zinc-800 dark:text-zinc-200";
}

export default function MigrationProcessChain() {
  return (
    <section
      aria-label="Этапы кадрового процесса"
      className="rounded-xl border border-zinc-200 bg-zinc-50/80 p-4 dark:border-zinc-800 dark:bg-zinc-900/40"
    >
      <h2 className="text-sm font-medium text-zinc-800 dark:text-zinc-200">Как устроен процесс</h2>
      <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-stretch">
        {MIGRATION_PROCESS_STEPS.map((step, index) => {
          const active = step.id === MIGRATION_CURRENT_STEP_ID;
          const content = (
            <>
              <span className={stepTitleClass(active)}>{step.title}</span>
              {active ? (
                <span className="mt-1 text-[11px] font-medium uppercase tracking-wide text-blue-700 dark:text-blue-300">
                  Текущий этап
                </span>
              ) : null}
            </>
          );

          return (
            <React.Fragment key={step.id}>
              {step.href && !active ? (
                <Link
                  href={step.href}
                  className={`${stepShellClass(false)} hover:border-zinc-300 dark:hover:border-zinc-700`}
                >
                  {content}
                </Link>
              ) : (
                <div className={stepShellClass(active)}>{content}</div>
              )}
              {index < MIGRATION_PROCESS_STEPS.length - 1 ? (
                <span
                  aria-hidden="true"
                  className="flex shrink-0 items-center justify-center text-zinc-400 sm:px-0 sm:py-0"
                >
                  <span className="hidden sm:inline">→</span>
                  <span className="sm:hidden">↓</span>
                </span>
              ) : null}
            </React.Fragment>
          );
        })}
      </div>
    </section>
  );
}
