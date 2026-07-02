// FILE: corpsite-ui/app/regular-tasks/_components/SchedulerStatusPanel.tsx
"use client";

import Link from "next/link";
import * as React from "react";

import {
  apiGetRegularTaskSchedulerStatus,
  type RegularTaskSchedulerStatus,
  type SchedulerPeriodDiagnostic,
} from "@/lib/api";
import { fmtDateTime } from "@/lib/regularTaskRunJournal";

type SchedulerStatusPanelProps = {
  /** full — templates page (with period diagnostics); compact — catch-up page */
  variant?: "full" | "compact";
};

type ResultTone = "success" | "warning" | "error" | "neutral";

function statusTone(status: string): string {
  switch (status) {
    case "working":
      return "text-emerald-800 dark:text-emerald-200";
    case "needs_attention":
      return "text-amber-900 dark:text-amber-200";
    default:
      return "text-red-700 dark:text-red-300";
  }
}

function statusIndicator(status: string): string {
  switch (status) {
    case "working":
      return "🟢";
    case "needs_attention":
      return "🟡";
    default:
      return "🔴";
  }
}

function resultBadgeClass(tone: ResultTone): string {
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

function resolveResultTone(status: RegularTaskSchedulerStatus | null): ResultTone {
  if (!status) return "neutral";
  if (status.last_error) return "error";
  if (status.status === "working") return "success";
  if (status.status === "needs_attention") return "warning";
  return "neutral";
}

function formatCheckedAt(value?: string | null): string {
  if (!value) return "—";
  return fmtDateTime(value);
}

function PeriodDiagnosticRow({ row }: { row: SchedulerPeriodDiagnostic }) {
  const periodLabel = row.period_display || row.label;
  const statusLabel = row.creation_status_label || (row.has_tasks ? "создан" : "не создан");
  const reason = row.primary_reason || row.likely_reasons?.[0];

  return (
    <div
      className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50/80 dark:bg-zinc-900/50 px-3 py-2"
      data-testid={`scheduler-period-${row.key}`}
    >
      <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">{row.title || row.schedule_type}</p>
      <dl className="mt-1 space-y-0.5 text-xs text-zinc-800 dark:text-zinc-200">
        <div className="flex flex-wrap gap-x-1.5">
          <dt className="text-zinc-600 dark:text-zinc-400">Период:</dt>
          <dd>{periodLabel}</dd>
        </div>
        <div className="flex flex-wrap gap-x-1.5">
          <dt className="text-zinc-600 dark:text-zinc-400">Статус:</dt>
          <dd
            className={
              row.has_tasks
                ? "text-emerald-800 dark:text-emerald-200"
                : "text-amber-900 dark:text-amber-200"
            }
          >
            {statusLabel}
          </dd>
        </div>
        {!row.has_tasks && reason ? (
          <div className="flex flex-col gap-0.5">
            <dt className="text-zinc-600 dark:text-zinc-400">Вероятная причина:</dt>
            <dd data-testid={`scheduler-period-reason-${row.key}`}>{reason}</dd>
          </div>
        ) : null}
      </dl>
      {row.last_run_item?.run_id ? (
        <p className="mt-1 text-[11px] text-zinc-500 dark:text-zinc-500">
          <Link
            href={`/regular-task-runs?run_id=${row.last_run_item.run_id}`}
            className="text-blue-700 hover:text-blue-600 dark:text-blue-300"
          >
            Журнал запуска #{row.last_run_item.run_id}
          </Link>
        </p>
      ) : null}
    </div>
  );
}

export default function SchedulerStatusPanel({ variant = "full" }: SchedulerStatusPanelProps) {
  const [status, setStatus] = React.useState<RegularTaskSchedulerStatus | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const loadStatus = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiGetRegularTaskSchedulerStatus();
      setStatus(data);
    } catch (e: any) {
      setStatus(null);
      setError(String(e?.message || "Не удалось загрузить состояние автоматического запуска."));
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  const resultTone = resolveResultTone(status);
  const showPeriodDiagnostics = variant === "full";
  const action = status?.recommended_action;
  const showAction = action && action.kind !== "none" && action.href;

  return (
    <section
      className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white/70 dark:bg-zinc-950/70 px-3 py-2 shadow-sm"
      data-testid="scheduler-status-panel"
      aria-label="Состояние автоматического запуска"
    >
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-zinc-600 dark:text-zinc-400">
              Автоматический запуск
            </h2>

            {loading ? (
              <span className="text-xs text-zinc-600 dark:text-zinc-400">Загрузка…</span>
            ) : error ? (
              <span className="text-xs text-red-700 dark:text-red-300">{error}</span>
            ) : status ? (
              <p
                className={["text-sm font-medium", statusTone(status.status)].join(" ")}
                data-testid="scheduler-status-badge"
              >
                {statusIndicator(status.status)} {status.status_label}
              </p>
            ) : null}
          </div>

          {!loading && !error && status?.status_explanation ? (
            <p
              className="mt-1 text-xs text-zinc-700 dark:text-zinc-300"
              data-testid="scheduler-status-explanation"
            >
              {status.status_explanation}
            </p>
          ) : null}

          {!loading && !error && status ? (
            <dl className="mt-2 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-zinc-800 dark:text-zinc-200">
              <div className="flex flex-wrap items-center gap-x-1.5">
                <dt className="text-zinc-600 dark:text-zinc-400">Последний запуск:</dt>
                <dd data-testid="scheduler-last-run">
                  {status.last_run_at ? fmtDateTime(status.last_run_at) : "—"}
                </dd>
              </div>
              <div className="flex flex-wrap items-center gap-x-1.5">
                <dt className="text-zinc-600 dark:text-zinc-400">Последний успешный:</dt>
                <dd data-testid="scheduler-last-success">
                  {status.last_successful_run_at ? fmtDateTime(status.last_successful_run_at) : "—"}
                </dd>
              </div>
              <div className="flex flex-wrap items-center gap-x-1.5">
                <dt className="text-zinc-600 dark:text-zinc-400">Последний результат:</dt>
                <dd>
                  <span
                    className={[
                      "inline-flex rounded-full border px-2 py-0.5 text-xs font-medium",
                      resultBadgeClass(resultTone),
                    ].join(" ")}
                    data-testid="scheduler-last-result"
                  >
                    {status.last_result_label}
                  </span>
                </dd>
              </div>
              {status.expected_next_run_label ? (
                <div className="flex flex-wrap items-center gap-x-1.5">
                  <dt className="text-zinc-600 dark:text-zinc-400">
                    {status.is_cron_overdue ? "Ожидался:" : "Следующий ожидаемый автоматический запуск:"}
                  </dt>
                  <dd data-testid="scheduler-next-run">{status.expected_next_run_label}</dd>
                </div>
              ) : null}
              {status.is_cron_overdue && (status.cron_overdue_days ?? 0) > 0 ? (
                <div className="flex flex-wrap items-center gap-x-1.5">
                  <dt className="text-zinc-600 dark:text-zinc-400">Просрочка:</dt>
                  <dd className="font-medium text-amber-900 dark:text-amber-200" data-testid="scheduler-overdue">
                    {status.cron_overdue_days} дн.
                  </dd>
                </div>
              ) : null}
            </dl>
          ) : null}

          {!loading && !error && status?.last_error ? (
            <p
              className="mt-1 text-xs text-red-700 dark:text-red-300"
              data-testid="scheduler-last-error"
            >
              Последняя ошибка: {status.last_error}
            </p>
          ) : null}

          {!loading && !error && status ? (
            <p className="mt-1 text-[11px] text-zinc-500 dark:text-zinc-500" data-testid="scheduler-hint">
              {status.hint}
            </p>
          ) : null}

          {!loading && !error && showAction ? (
            <div className="mt-2" data-testid="scheduler-recommended-action">
              <p className="text-xs font-medium text-zinc-700 dark:text-zinc-300">Следующее действие:</p>
              <Link
                href={action.href!}
                className="mt-1 inline-flex text-sm font-medium text-blue-700 hover:text-blue-600 dark:text-blue-300"
              >
                → {action.label}
              </Link>
            </div>
          ) : null}

          <p
            className="mt-0.5 text-[11px] text-zinc-500 dark:text-zinc-500"
            data-testid="scheduler-data-source"
          >
            Источник данных: GET /regular-tasks/scheduler-status
            {status?.checked_at ? ` · обновлено ${formatCheckedAt(status.checked_at)}` : ""}
          </p>

          {showPeriodDiagnostics && !loading && !error && status?.period_diagnostics?.length ? (
            <div className="mt-2 space-y-2" data-testid="scheduler-period-diagnostics">
              <p className="text-xs font-medium text-zinc-700 dark:text-zinc-300">
                Диагностика пропущенных периодов
              </p>
              {status.period_diagnostics.map((row) => (
                <PeriodDiagnosticRow key={row.key} row={row} />
              ))}
            </div>
          ) : null}
        </div>

        <div className="flex shrink-0 flex-col items-end gap-1">
          <button
            type="button"
            onClick={() => void loadStatus()}
            disabled={loading}
            className="rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white/60 dark:bg-zinc-900/60 px-3 py-1.5 text-xs font-medium text-zinc-900 dark:text-zinc-50 transition hover:bg-zinc-200 disabled:opacity-60 dark:hover:bg-zinc-700"
            data-testid="scheduler-refresh-button"
          >
            {loading ? "Обновление…" : "Обновить статус"}
          </button>
          <Link
            href="/regular-task-runs"
            className="text-xs font-medium text-blue-700 transition hover:text-blue-600 dark:text-blue-300 dark:hover:text-blue-200"
            data-testid="scheduler-journal-link"
          >
            Журнал запусков →
          </Link>
          {showPeriodDiagnostics ? (
            <Link
              href="/admin/regular-tasks/catch-up"
              className="text-xs font-medium text-blue-700 transition hover:text-blue-600 dark:text-blue-300 dark:hover:text-blue-200"
              data-testid="scheduler-catch-up-link"
            >
              Догоняющий запуск →
            </Link>
          ) : null}
        </div>
      </div>
    </section>
  );
}
