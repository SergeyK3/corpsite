// FILE: corpsite-ui/app/admin/system/_components/TelegramStatusPanel.tsx
"use client";

import * as React from "react";

import {
  fetchTelegramHealth,
  mapAdminSystemApiError,
} from "../_lib/adminSystemApi.client";
import {
  buildTelegramStatusView,
  formatConfiguredLabel,
  TELEGRAM_HEALTH_REFRESH_MS,
  TELEGRAM_UNAVAILABLE_METRIC_IDS,
  type TelegramHealthResponse,
  type TelegramHealthStatus,
} from "@/lib/telegramHealthStatus";
import { fmtDateTime } from "@/lib/regularTaskRunJournal";

type TelegramStatusPanelProps = {
  refreshIntervalMs?: number;
};

function statusTone(status: TelegramHealthStatus): string {
  switch (status) {
    case "GREEN":
      return "text-emerald-800 dark:text-emerald-200";
    case "YELLOW":
      return "text-amber-900 dark:text-amber-200";
    default:
      return "text-red-700 dark:text-red-300";
  }
}

function statusIndicator(status: TelegramHealthStatus): string {
  switch (status) {
    case "GREEN":
      return "🟢";
    case "YELLOW":
      return "🟡";
    default:
      return "🔴";
  }
}

function chipClass(tone: "neutral" | "warn" | "danger" | "success"): string {
  switch (tone) {
    case "success":
      return "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-200";
    case "warn":
      return "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-200";
    case "danger":
      return "border-red-200 bg-red-50 text-red-700 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-300";
    default:
      return "border-zinc-200 bg-zinc-100 text-zinc-700 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300";
  }
}

function queueChipTone(name: "pending" | "sent" | "failed", value: number): "neutral" | "warn" | "danger" | "success" {
  if (name === "pending") return value > 0 ? "warn" : "neutral";
  if (name === "failed") return value > 0 ? "danger" : "neutral";
  return value > 0 ? "success" : "neutral";
}

function MetricChip({
  label,
  value,
  tone,
  testId,
}: {
  label: string;
  value: string | number;
  tone: "neutral" | "warn" | "danger" | "success";
  testId?: string;
}) {
  return (
    <span
      className={["inline-flex rounded-full border px-2 py-0.5 text-xs font-medium", chipClass(tone)].join(" ")}
      data-testid={testId}
    >
      {label}: {value}
    </span>
  );
}

function PanelBody({ data }: { data: TelegramHealthResponse }) {
  const view = React.useMemo(() => buildTelegramStatusView(data), [data]);
  const cfg = data.bot_configuration;
  const unavailableDetails = (data.unavailable_metrics ?? [])
    .map((item) => `${item.metric}: ${item.reason}`)
    .join("\n");

  return (
    <>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <p
          className={["text-sm font-medium", statusTone(view.status)].join(" ")}
          data-testid="telegram-status-badge"
        >
          {statusIndicator(view.status)} {view.status_label}
        </p>
        <span className="text-xs text-zinc-600 dark:text-zinc-400" data-testid="telegram-checked-at">
          Проверено: {view.checked_at_label}
        </span>
      </div>

      <div className="mt-2 flex flex-wrap gap-2" data-testid="telegram-queue-chips">
        <MetricChip
          label="Pending"
          value={data.queue.pending_count}
          tone={queueChipTone("pending", data.queue.pending_count)}
          testId="telegram-chip-pending"
        />
        <MetricChip
          label="Sent 24h"
          value={data.queue.sent_24h}
          tone={queueChipTone("sent", data.queue.sent_24h)}
          testId="telegram-chip-sent"
        />
        <MetricChip
          label="Failed 24h"
          value={data.queue.failed_24h}
          tone={queueChipTone("failed", data.queue.failed_24h)}
          testId="telegram-chip-failed"
        />
        {data.queue.oldest_pending_age_sec != null ? (
          <MetricChip
            label="Oldest pending"
            value={view.oldest_pending_age_label}
            tone={data.queue.pending_count > 0 ? "warn" : "neutral"}
            testId="telegram-chip-oldest-pending"
          />
        ) : null}
      </div>

      <dl className="mt-2 grid gap-1 text-xs text-zinc-800 dark:text-zinc-200 sm:grid-cols-2">
        <div>
          <dt className="text-zinc-600 dark:text-zinc-400">Последняя успешная отправка</dt>
          <dd data-testid="telegram-last-sent">{fmtDateTime(data.delivery.last_sent_at)}</dd>
        </div>
        {data.delivery.last_failed_at ? (
          <div>
            <dt className="text-zinc-600 dark:text-zinc-400">Последняя ошибка</dt>
            <dd data-testid="telegram-last-failed">{fmtDateTime(data.delivery.last_failed_at)}</dd>
          </div>
        ) : null}
        {data.delivery.last_error_code || data.delivery.last_error_text ? (
          <div className="sm:col-span-2">
            <dt className="text-zinc-600 dark:text-zinc-400">Код / текст ошибки</dt>
            <dd data-testid="telegram-last-error">
              {[data.delivery.last_error_code, data.delivery.last_error_text].filter(Boolean).join(" — ")}
            </dd>
          </div>
        ) : null}
        <div>
          <dt className="text-zinc-600 dark:text-zinc-400">Привязки Telegram</dt>
          <dd data-testid="telegram-bindings">
            {data.bindings.users_with_telegram} / {data.bindings.active_users} ({data.bindings.coverage_percent}%)
          </dd>
        </div>
      </dl>

      {view.show_coverage_warning ? (
        <p
          className="mt-2 text-xs text-amber-900 dark:text-amber-200"
          data-testid="telegram-coverage-warning"
        >
          Не у всех активных пользователей привязан Telegram
        </p>
      ) : null}

      <dl className="mt-2 grid gap-1 text-[11px] text-zinc-700 dark:text-zinc-300 sm:grid-cols-2">
        <div>
          <dt className="text-zinc-500 dark:text-zinc-500">BOT_TOKEN</dt>
          <dd data-testid="telegram-config-bot-token">{formatConfiguredLabel(cfg.bot_token_present)}</dd>
        </div>
        <div>
          <dt className="text-zinc-500 dark:text-zinc-500">INTERNAL_API_TOKEN</dt>
          <dd data-testid="telegram-config-internal-token">
            {formatConfiguredLabel(cfg.internal_api_token_present)}
          </dd>
        </div>
        <div>
          <dt className="text-zinc-500 dark:text-zinc-500">BOT_BIND_TOKEN</dt>
          <dd data-testid="telegram-config-bind-token">{formatConfiguredLabel(cfg.bot_bind_token_present)}</dd>
        </div>
        <div>
          <dt className="text-zinc-500 dark:text-zinc-500">API_BASE_URL</dt>
          <dd data-testid="telegram-config-api-base">{cfg.api_base_url ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-zinc-500 dark:text-zinc-500">EVENTS_DELIVERY_CHANNEL</dt>
          <dd data-testid="telegram-config-channel">{cfg.events_delivery_channel}</dd>
        </div>
        <div>
          <dt className="text-zinc-500 dark:text-zinc-500">Allow-list</dt>
          <dd data-testid="telegram-config-allowlist">
            {cfg.telegram_delivery_allowlist_configured ? "да" : "нет"}
          </dd>
        </div>
      </dl>

      {data.status_reasons && data.status_reasons.length > 0 ? (
        <ul className="mt-2 list-disc space-y-0.5 pl-4 text-xs text-zinc-800 dark:text-zinc-200" data-testid="telegram-status-reasons">
          {data.status_reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      ) : null}

      <p
        className="mt-2 text-[11px] text-zinc-500 dark:text-zinc-500"
        title={
          unavailableDetails ||
          TELEGRAM_UNAVAILABLE_METRIC_IDS.map((metric) => `${metric}: backend-only API`).join("\n")
        }
        data-testid="telegram-unavailable-metrics"
      >
        Часть метрик недоступна из backend-only API
      </p>

      <p className="mt-1 text-[11px] text-zinc-500 dark:text-zinc-500" data-testid="telegram-data-source">
        Источник данных: GET /admin/system/telegram-health
      </p>
    </>
  );
}

export default function TelegramStatusPanel({
  refreshIntervalMs = TELEGRAM_HEALTH_REFRESH_MS,
}: TelegramStatusPanelProps) {
  const [data, setData] = React.useState<TelegramHealthResponse | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [refreshing, setRefreshing] = React.useState(false);

  const load = React.useCallback(async (opts?: { background?: boolean }) => {
    const background = opts?.background ?? false;
    if (!background) setLoading(true);
    else setRefreshing(true);
    setError(null);
    try {
      const payload = await fetchTelegramHealth();
      setData(payload);
    } catch (err: unknown) {
      const status = (err as { status?: number })?.status;
      if (status === 403) {
        setError("Недостаточно прав для просмотра статуса Telegram");
      } else if (status === 401) {
        setError("Требуется авторизация для просмотра статуса Telegram");
      } else {
        setError(mapAdminSystemApiError(err, "Не удалось загрузить статус Telegram"));
      }
      setData(null);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  React.useEffect(() => {
    void load();
    const timer = window.setInterval(() => {
      void load({ background: true });
    }, refreshIntervalMs);
    return () => window.clearInterval(timer);
  }, [load, refreshIntervalMs]);

  return (
    <section
      className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white/70 dark:bg-zinc-950/70 px-3 py-2 shadow-sm"
      data-testid="telegram-status-panel"
      aria-label="Состояние Telegram-бота"
    >
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-zinc-600 dark:text-zinc-400">
              Telegram-бот
            </h2>
            {loading ? (
              <span className="text-xs text-zinc-600 dark:text-zinc-400" data-testid="telegram-loading">
                Загрузка статуса Telegram…
              </span>
            ) : error ? (
              <span className="text-xs text-red-700 dark:text-red-300" data-testid="telegram-error">
                {error}
              </span>
            ) : null}
          </div>

          {!loading && !error && data ? <PanelBody data={data} /> : null}
        </div>

        <button
          type="button"
          onClick={() => void load({ background: true })}
          disabled={loading || refreshing}
          className="shrink-0 text-xs font-medium text-blue-700 transition hover:text-blue-600 disabled:opacity-50 dark:text-blue-300 dark:hover:text-blue-200"
          data-testid="telegram-refresh-button"
        >
          {refreshing ? "Обновление…" : "Обновить"}
        </button>
      </div>
    </section>
  );
}

export { PanelBody as TelegramStatusPanelBodyForTests };
