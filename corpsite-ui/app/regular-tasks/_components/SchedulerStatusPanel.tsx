// FILE: corpsite-ui/app/regular-tasks/_components/SchedulerStatusPanel.tsx
"use client";

import Link from "next/link";
import * as React from "react";

import { buildSchedulerStatusView } from "@/lib/regularTaskSchedulerStatus";
import type { RegularTaskRunRow } from "@/lib/regularTaskRunJournal";

type SchedulerStatusPanelProps = {
  runs: readonly RegularTaskRunRow[];
  loading?: boolean;
  error?: string | null;
};

function statusTone(status: ReturnType<typeof buildSchedulerStatusView>["status"]): string {
  switch (status) {
    case "working":
      return "text-emerald-800 dark:text-emerald-200";
    case "needs_attention":
      return "text-amber-900 dark:text-amber-200";
    default:
      return "text-red-700 dark:text-red-300";
  }
}

function statusIndicator(status: ReturnType<typeof buildSchedulerStatusView>["status"]): string {
  switch (status) {
    case "working":
      return "🟢";
    case "needs_attention":
      return "🟡";
    default:
      return "🔴";
  }
}

export default function SchedulerStatusPanel({
  runs,
  loading = false,
  error = null,
}: SchedulerStatusPanelProps) {
  const view = React.useMemo(() => buildSchedulerStatusView(runs), [runs]);

  return (
    <section
      className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white/70 dark:bg-zinc-950/70 px-4 py-3 shadow-sm"
      data-testid="scheduler-status-panel"
      aria-label="Состояние автоматического запуска"
    >
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 flex-1 space-y-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-600 dark:text-zinc-400">
            Автоматический запуск
          </h2>

          {loading ? (
            <p className="text-sm text-zinc-600 dark:text-zinc-400">Загрузка состояния…</p>
          ) : error ? (
            <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
          ) : (
            <>
              <p
                className={["text-base font-medium", statusTone(view.status)].join(" ")}
                data-testid="scheduler-status-badge"
              >
                {statusIndicator(view.status)} {view.status_label}
              </p>

              <dl className="grid gap-1 text-sm text-zinc-800 dark:text-zinc-200 sm:grid-cols-1">
                <div className="flex flex-wrap gap-x-2">
                  <dt className="text-zinc-600 dark:text-zinc-400">Последний запуск:</dt>
                  <dd data-testid="scheduler-last-run">{view.last_run_at_label}</dd>
                </div>
                <div className="flex flex-wrap gap-x-2">
                  <dt className="text-zinc-600 dark:text-zinc-400">Последний успешный запуск:</dt>
                  <dd data-testid="scheduler-last-success">{view.last_successful_run_at_label}</dd>
                </div>
                <div className="flex flex-wrap gap-x-2">
                  <dt className="text-zinc-600 dark:text-zinc-400">Последний результат:</dt>
                  <dd data-testid="scheduler-last-result">{view.last_result_label}</dd>
                </div>
              </dl>
            </>
          )}
        </div>

        <Link
          href="/regular-task-runs"
          className="shrink-0 text-sm font-medium text-blue-700 transition hover:text-blue-600 dark:text-blue-300 dark:hover:text-blue-200"
          data-testid="scheduler-journal-link"
        >
          Открыть журнал запусков →
        </Link>
      </div>
    </section>
  );
}
