// FILE: corpsite-ui/lib/telegramHealthStatus.ts

import { fmtDateTime } from "./regularTaskRunJournal";

export type TelegramHealthStatus = "GREEN" | "YELLOW" | "RED";

export type TelegramHealthQueue = {
  pending_count: number;
  sent_24h: number;
  failed_24h: number;
  oldest_pending_at?: string | null;
  oldest_pending_age_sec?: number | null;
};

export type TelegramHealthDelivery = {
  last_sent_at?: string | null;
  last_failed_at?: string | null;
  last_error_code?: string | null;
  last_error_text?: string | null;
};

export type TelegramHealthBindings = {
  active_users: number;
  users_with_telegram: number;
  coverage_percent: number;
};

export type TelegramHealthBotConfiguration = {
  bot_token_present: boolean;
  internal_api_token_present: boolean;
  bot_bind_token_present: boolean;
  api_base_url?: string | null;
  events_delivery_channel: string;
  events_internal_api_user_id?: string | null;
  telegram_delivery_allowlist_configured: boolean;
};

export type TelegramHealthUnavailableMetric = {
  metric: string;
  reason: string;
};

export type TelegramHealthResponse = {
  checked_at: string;
  channel: string;
  window_hours: number;
  status: TelegramHealthStatus;
  status_reasons?: string[];
  queue: TelegramHealthQueue;
  delivery: TelegramHealthDelivery;
  bindings: TelegramHealthBindings;
  bot_configuration: TelegramHealthBotConfiguration;
  error_summary?: {
    error_code?: string | null;
    occurred_at?: string | null;
    message?: string | null;
  } | null;
  unavailable_metrics?: TelegramHealthUnavailableMetric[];
};

export type TelegramStatusView = {
  status: TelegramHealthStatus;
  status_label: string;
  service_status: TelegramHealthStatus;
  service_status_label: string;
  checked_at_label: string;
  oldest_pending_age_label: string;
  coverage_label: string;
  show_coverage_warning: boolean;
  operational_reasons: string[];
  unavailable_metric_ids: string[];
};

const STATUS_LABELS: Record<TelegramHealthStatus, string> = {
  GREEN: "Работает",
  YELLOW: "Требует внимания",
  RED: "Не работает",
};

const SERVICE_STATUS_LABELS: Record<TelegramHealthStatus, string> = {
  GREEN: "Работает",
  YELLOW: "Есть предупреждения",
  RED: "Не работает",
};

export const TELEGRAM_HEALTH_REFRESH_MS = 45_000;

export const TELEGRAM_UNAVAILABLE_METRIC_IDS = [
  "bot_service_active",
  "bot_service_uptime",
  "bot_journal_errors",
  "telegram_api_reachable",
  "delivery_queue_poll_lag",
] as const;

export function telegramHealthStatusLabel(status: TelegramHealthStatus): string {
  return STATUS_LABELS[status] ?? status;
}

export function telegramServiceStatusLabel(status: TelegramHealthStatus): string {
  return SERVICE_STATUS_LABELS[status] ?? status;
}

export function isCoverageStatusReason(reason: string): boolean {
  return /Telegram binding coverage is/i.test(reason);
}

export function formatCoveragePercent(percent: number): string {
  return `${percent.toLocaleString("ru-RU", { maximumFractionDigits: 1, minimumFractionDigits: 0 })}%`;
}

export function formatBindingsCoverageLabel(bindings: TelegramHealthBindings): string {
  return `${bindings.users_with_telegram} из ${bindings.active_users} пользователей (${formatCoveragePercent(bindings.coverage_percent)})`;
}

export function deriveTelegramServiceStatus(data: TelegramHealthResponse): {
  status: TelegramHealthStatus;
  status_label: string;
  operational_reasons: string[];
} {
  const operationalReasons = (data.status_reasons ?? []).filter((reason) => !isCoverageStatusReason(reason));

  if (data.status === "RED") {
    return {
      status: "RED",
      status_label: SERVICE_STATUS_LABELS.RED,
      operational_reasons: operationalReasons,
    };
  }

  if (data.status === "GREEN") {
    return {
      status: "GREEN",
      status_label: SERVICE_STATUS_LABELS.GREEN,
      operational_reasons: [],
    };
  }

  if (operationalReasons.length === 0) {
    return {
      status: "GREEN",
      status_label: SERVICE_STATUS_LABELS.GREEN,
      operational_reasons: [],
    };
  }

  return {
    status: "YELLOW",
    status_label: SERVICE_STATUS_LABELS.YELLOW,
    operational_reasons: operationalReasons,
  };
}

export function formatConfiguredLabel(present: boolean): string {
  return present ? "настроен" : "не настроен";
}

export function formatDurationSeconds(seconds?: number | null): string {
  if (seconds == null || !Number.isFinite(seconds) || seconds < 0) return "—";
  const total = Math.floor(seconds);
  if (total < 60) return `${total} сек`;
  const minutes = Math.floor(total / 60);
  if (minutes < 60) return `${minutes} мин`;
  const hours = Math.floor(minutes / 60);
  const remMin = minutes % 60;
  if (remMin === 0) return `${hours} ч`;
  return `${hours} ч ${remMin} мин`;
}

export function buildTelegramStatusView(data: TelegramHealthResponse): TelegramStatusView {
  const activeUsers = Number(data.bindings?.active_users ?? 0);
  const coverage = Number(data.bindings?.coverage_percent ?? 0);
  const service = deriveTelegramServiceStatus(data);

  return {
    status: data.status,
    status_label: telegramHealthStatusLabel(data.status),
    service_status: service.status,
    service_status_label: service.status_label,
    checked_at_label: fmtDateTime(data.checked_at),
    oldest_pending_age_label: formatDurationSeconds(data.queue?.oldest_pending_age_sec),
    coverage_label: formatBindingsCoverageLabel(data.bindings),
    show_coverage_warning: activeUsers > 0 && coverage < 100,
    operational_reasons: service.operational_reasons,
    unavailable_metric_ids: (data.unavailable_metrics ?? []).map((item) => item.metric),
  };
}

export function resolveTelegramHealthErrorMessage(err: unknown): string {
  const status = (err as { status?: number })?.status;
  if (status === 403) {
    return "Недостаточно прав для просмотра статуса Telegram";
  }
  if (status === 401) {
    return "Требуется авторизация для просмотра статуса Telegram";
  }
  return "Не удалось загрузить статус Telegram";
}

/** Test helper / docs fixture mirroring production YELLOW smoke (OPS-026.3). */
export function productionYellowSmokeFixture(): TelegramHealthResponse {
  return {
    checked_at: "2026-06-25T10:30:00+00:00",
    channel: "telegram",
    window_hours: 24,
    status: "YELLOW",
    status_reasons: ["Telegram binding coverage is 66.67%"],
    queue: {
      pending_count: 0,
      sent_24h: 16,
      failed_24h: 0,
      oldest_pending_at: null,
      oldest_pending_age_sec: null,
    },
    delivery: {
      last_sent_at: "2026-06-25T10:15:00+00:00",
      last_failed_at: null,
      last_error_code: null,
      last_error_text: null,
    },
    bindings: {
      active_users: 9,
      users_with_telegram: 6,
      coverage_percent: 66.67,
    },
    bot_configuration: {
      bot_token_present: true,
      internal_api_token_present: true,
      bot_bind_token_present: true,
      api_base_url: "http://127.0.0.1:8000",
      events_delivery_channel: "telegram",
      events_internal_api_user_id: "1",
      telegram_delivery_allowlist_configured: false,
    },
    error_summary: null,
    unavailable_metrics: TELEGRAM_UNAVAILABLE_METRIC_IDS.map((metric) => ({
      metric,
      reason: "Requires host access",
    })),
  };
}
