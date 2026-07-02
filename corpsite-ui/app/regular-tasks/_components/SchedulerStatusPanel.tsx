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
      return "⚠";
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

function formatOverdueDays(days: number): string {
  const mod10 = days % 10;
  const mod100 = days % 100;
  if (mod10 === 1 && mod100 !== 11) return `${days} день`;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return `${days} дня`;
  return `${days} дней`;
}

function formatCreationStatus(row: SchedulerPeriodDiagnostic): { icon: string; label: string } {
  if (row.has_tasks) {
    return { icon: "✓", label: "Создан" };
  }
  const raw = (row.creation_status_label || "не создан").trim();
  const label = raw.charAt(0).toUpperCase() + raw.slice(1);
  return { icon: "✖", label };
}

function resolvePeriodReason(row: SchedulerPeriodDiagnostic): { label: string; text: string } | null {
  if (row.has_tasks) return null;

  const reason = row.primary_reason || row.likely_reasons?.[0];
  if (!reason) return null;

  return {
    label: row.primary_reason ? "Причина" : "Вероятная причина",
    text: reason,
  };
}

function summarizeMissedPeriods(rows: SchedulerPeriodDiagnostic[]): SchedulerPeriodDiagnostic[] {
  return rows.filter((row) => !row.has_tasks);
}

function periodTypeLabel(row: SchedulerPeriodDiagnostic): string {
  return row.title || row.schedule_type;
}

function periodRangeLabel(row: SchedulerPeriodDiagnostic): string {
  return row.period_display || row.label;
}

function PeriodDiagnosticsSummary({ rows }: { rows: SchedulerPeriodDiagnostic[] }) {
  const missed = summarizeMissedPeriods(rows);

  if (missed.length === 0) {
    return (
      <p
        className="text-xs font-medium text-emerald-800 dark:text-emerald-200"
        data-testid="scheduler-period-summary"
      >
        ✓ Пропущенных периодов не обнаружено
      </p>
    );
  }

  return (
    <div
      className="rounded-lg border border-amber-200/80 bg-amber-50/50 px-2.5 py-2 dark:border-amber-900/40 dark:bg-amber-950/20"
      data-testid="scheduler-period-summary"
    >
      <p className="text-xs font-semibold text-amber-950 dark:text-amber-100">
        Пропущено периодов: {missed.length}
      </p>
      <ul className="mt-1 space-y-0.5 text-xs text-zinc-800 dark:text-zinc-200">
        {missed.map((row) => (
          <li key={row.key} data-testid={`scheduler-period-summary-item-${row.key}`}>
            • {periodTypeLabel(row)} — {periodRangeLabel(row)}
          </li>
        ))}
      </ul>
    </div>
  );
}

function FactRow({
  label,
  children,
  testId,
  highlight = false,
}: {
  label: string;
  children: React.ReactNode;
  testId?: string;
  highlight?: boolean;
}) {
  return (
    <div className="grid grid-cols-[minmax(0,11rem)_1fr] gap-x-3 gap-y-0.5 text-xs">
      <dt className="text-zinc-600 dark:text-zinc-400">{label}</dt>
      <dd
        className={highlight ? "font-semibold text-amber-950 dark:text-amber-100" : "text-zinc-900 dark:text-zinc-100"}
        data-testid={testId}
      >
        {children}
      </dd>
    </div>
  );
}

function PeriodDiagnosticRow({ row }: { row: SchedulerPeriodDiagnostic }) {
  const periodLabel = row.period_display || row.label;
  const creation = formatCreationStatus(row);
  const reason = resolvePeriodReason(row);

  return (
    <div
      className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50/80 dark:bg-zinc-900/50 px-3 py-2"
      data-testid={`scheduler-period-${row.key}`}
    >
      <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">{row.title || row.schedule_type}</p>
      <dl className="mt-1.5 space-y-1 text-xs">
        <FactRow label="Период:">{periodLabel}</FactRow>
        <FactRow label="Статус:" testId={`scheduler-period-status-${row.key}`}>
          <span
            className={
              row.has_tasks
                ? "text-emerald-800 dark:text-emerald-200"
                : "font-medium text-amber-900 dark:text-amber-200"
            }
          >
            {creation.icon} {creation.label}
          </span>
        </FactRow>
        {reason ? (
          <FactRow label={`${reason.label}:`} testId={`scheduler-period-reason-${row.key}`}>
            {reason.text}
          </FactRow>
        ) : null}
      </dl>
      {row.last_run_item?.run_id ? (
        <p className="mt-1.5 text-[11px] text-zinc-500 dark:text-zinc-500">
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
  const overdueDays = status?.cron_overdue_days ?? 0;
  const showOverdue = Boolean(status?.is_cron_overdue && overdueDays > 0);

  return (
    <section
      className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white/70 dark:bg-zinc-950/70 px-3 py-2 shadow-sm"
      data-testid="scheduler-status-panel"
      aria-label="Состояние автоматического запуска"
    >
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="min-w-0 flex-1 space-y-2">
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
                className={["text-sm font-semibold", statusTone(status.status)].join(" ")}
                data-testid="scheduler-status-badge"
              >
                {statusIndicator(status.status)} {status.status_label}
              </p>
            ) : null}
          </div>

          {!loading && !error && status ? (
            <>
              <div data-testid="scheduler-summary-block">
                <p className="text-xs font-semibold uppercase tracking-wide text-zinc-600 dark:text-zinc-400">
                  Причина
                </p>
                <dl className="mt-1 space-y-1">
                  <FactRow label="Последний автоматический запуск:" testId="scheduler-last-run">
                    {status.last_run_at ? fmtDateTime(status.last_run_at) : "—"}
                  </FactRow>
                  {showOverdue ? (
                    <FactRow label="Просрочка:" testId="scheduler-overdue" highlight>
                      <span
                        className="inline-flex items-center rounded-md border border-amber-300 bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-950 dark:border-amber-700 dark:bg-amber-950/60 dark:text-amber-100"
                        data-testid="scheduler-overdue-badge"
                      >
                        {formatOverdueDays(overdueDays)}
                      </span>
                    </FactRow>
                  ) : null}
                  <FactRow label="Последний успешный запуск:" testId="scheduler-last-success">
                    {status.last_successful_run_at ? fmtDateTime(status.last_successful_run_at) : "—"}
                  </FactRow>
                  {status.expected_next_run_label ? (
                    <FactRow
                      label={status.is_cron_overdue ? "Ожидался:" : "Следующий ожидаемый автоматический запуск:"}
                      testId="scheduler-next-run"
                    >
                      {status.expected_next_run_label}
                    </FactRow>
                  ) : null}
                  <FactRow label="Последний результат:">
                    <span
                      className={[
                        "inline-flex rounded-full border px-2 py-0.5 text-xs font-medium",
                        resultBadgeClass(resultTone),
                      ].join(" ")}
                      data-testid="scheduler-last-result"
                    >
                      {status.last_result_label}
                    </span>
                  </FactRow>
                </dl>
              </div>

              {status.status_explanation ? (
                <p
                  className="rounded-lg border border-zinc-200/80 bg-zinc-50/80 px-2.5 py-2 text-xs leading-relaxed text-zinc-700 dark:border-zinc-800 dark:bg-zinc-900/40 dark:text-zinc-300"
                  data-testid="scheduler-status-explanation"
                >
                  {status.status_explanation}
                </p>
              ) : null}

              {showAction ? (
                <div
                  className="rounded-lg border border-blue-200/80 bg-blue-50/50 px-2.5 py-2 dark:border-blue-900/40 dark:bg-blue-950/20"
                  data-testid="scheduler-recommended-action"
                >
                  <p className="text-xs font-semibold text-zinc-800 dark:text-zinc-200">Следующее действие</p>
                  <Link
                    href={action.href!}
                    className="mt-1 inline-flex text-sm font-medium text-blue-700 hover:text-blue-600 dark:text-blue-300"
                  >
                    → {action.label}
                  </Link>
                </div>
              ) : null}

              {showPeriodDiagnostics ? (
                <div className="space-y-2" data-testid="scheduler-period-diagnostics">
                  <p className="text-xs font-semibold text-zinc-800 dark:text-zinc-200">
                    Диагностика пропущенных периодов
                  </p>
                  <PeriodDiagnosticsSummary rows={status.period_diagnostics ?? []} />
                  {(status.period_diagnostics ?? []).map((row) => (
                    <PeriodDiagnosticRow key={row.key} row={row} />
                  ))}
                </div>
              ) : null}

              <div
                className="space-y-1 border-t border-zinc-200/80 pt-2 dark:border-zinc-800"
                data-testid="scheduler-technical-details"
              >
                <p className="text-[11px] font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-500">
                  Технические сведения
                </p>
                {status.last_error ? (
                  <p className="text-xs text-red-700 dark:text-red-300" data-testid="scheduler-last-error">
                    Последняя ошибка: {status.last_error}
                  </p>
                ) : null}
                <p className="text-[11px] leading-relaxed text-zinc-500 dark:text-zinc-500" data-testid="scheduler-hint">
                  {status.hint}
                </p>
                <p className="text-[11px] text-zinc-500 dark:text-zinc-500" data-testid="scheduler-manual-run-note">
                  Ручной запуск генерации (`POST /internal/regular-tasks/run`) на странице шаблонов вызывает тот же
                  механизм, что и cron, но с `trigger_source=manual` и только для шаблонов, due на сегодня. Он не
                  восполняет пропущенные отчётные периоды — для этого используйте догоняющий запуск.
                </p>
                <p className="text-[11px] text-zinc-500 dark:text-zinc-500" data-testid="scheduler-data-source">
                  Источник данных: GET /regular-tasks/scheduler-status
                  {status.checked_at ? ` · обновлено ${formatCheckedAt(status.checked_at)}` : ""}
                </p>
              </div>
            </>
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
