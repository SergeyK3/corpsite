// FILE: corpsite-ui/app/regular-tasks/_components/SchedulerStatusPanel.tsx
"use client";

import Link from "next/link";
import * as React from "react";

import {
  buildSchedulerStatusView,
  type SchedulerResultTone,
} from "@/lib/regularTaskSchedulerStatus";
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

function resultBadgeClass(tone: SchedulerResultTone): string {
  switch (tone) {
    case "success":
      return "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-200";
    case "warning":
      return "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-200";
    case "error":
      return "border-red-200 bg-red-50 text-red-700 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-300";
    default:
      return "border-zinc-200 bg-zinc-100 text-zinc-700 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300";
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
      className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white/70 dark:bg-zinc-950/70 px-3 py-2 shadow-sm"
      data-testid="scheduler-status-panel"
      aria-label="Состояние автоматического запуска"
    >
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-zinc-600 dark:text-zinc-400">
              Автоматический запуск
            </h2>

            {loading ? (
              <span className="text-xs text-zinc-600 dark:text-zinc-400">Загрузка…</span>
            ) : error ? (
              <span className="text-xs text-red-700 dark:text-red-300">{error}</span>
            ) : (
              <p
                className={["text-sm font-medium", statusTone(view.status)].join(" ")}
                data-testid="scheduler-status-badge"
              >
                {statusIndicator(view.status)} {view.status_label}
              </p>
            )}
          </div>

          {!loading && !error ? (
            <dl className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-zinc-800 dark:text-zinc-200">
              <div className="flex flex-wrap items-center gap-x-1.5">
                <dt className="text-zinc-600 dark:text-zinc-400">Последний запуск:</dt>
                <dd data-testid="scheduler-last-run">{view.last_run_at_label}</dd>
              </div>
              <div className="flex flex-wrap items-center gap-x-1.5">
                <dt className="text-zinc-600 dark:text-zinc-400">Последний успешный запуск:</dt>
                <dd data-testid="scheduler-last-success">{view.last_successful_run_at_label}</dd>
              </div>
              <div className="flex flex-wrap items-center gap-x-1.5">
                <dt className="text-zinc-600 dark:text-zinc-400">Последний результат:</dt>
                <dd>
                  <span
                    className={[
                      "inline-flex rounded-full border px-2 py-0.5 text-xs font-medium",
                      resultBadgeClass(view.last_result_tone),
                    ].join(" ")}
                    data-testid="scheduler-last-result"
                  >
                    {view.last_result_label}
                  </span>
                </dd>
              </div>
            </dl>
          ) : null}

          <p
            className="mt-1 text-[11px] text-zinc-500 dark:text-zinc-500"
            data-testid="scheduler-data-source"
          >
            Источник данных: журнал автоматических запусков
          </p>
        </div>

        <Link
          href="/regular-task-runs"
          className="shrink-0 text-xs font-medium text-blue-700 transition hover:text-blue-600 dark:text-blue-300 dark:hover:text-blue-200"
          data-testid="scheduler-journal-link"
        >
          Открыть журнал запусков →
        </Link>
      </div>
    </section>
  );
}
