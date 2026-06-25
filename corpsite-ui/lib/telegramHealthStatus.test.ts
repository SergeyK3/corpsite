// FILE: corpsite-ui/lib/telegramHealthStatus.test.ts

import { describe, expect, it } from "vitest";

import {
  buildTelegramStatusView,
  deriveTelegramServiceStatus,
  formatBindingsCoverageLabel,
  formatConfiguredLabel,
  formatCoveragePercent,
  formatDurationSeconds,
  isCoverageStatusReason,
  productionYellowSmokeFixture,
  telegramHealthStatusLabel,
  telegramServiceStatusLabel,
} from "./telegramHealthStatus";

describe("telegramHealthStatus", () => {
  it("maps health status labels", () => {
    expect(telegramHealthStatusLabel("GREEN")).toBe("Работает");
    expect(telegramHealthStatusLabel("YELLOW")).toBe("Требует внимания");
    expect(telegramHealthStatusLabel("RED")).toBe("Не работает");
  });

  it("maps service status labels", () => {
    expect(telegramServiceStatusLabel("GREEN")).toBe("Работает");
    expect(telegramServiceStatusLabel("YELLOW")).toBe("Есть предупреждения");
    expect(telegramServiceStatusLabel("RED")).toBe("Не работает");
  });

  it("formats configured labels", () => {
    expect(formatConfiguredLabel(true)).toBe("настроен");
    expect(formatConfiguredLabel(false)).toBe("не настроен");
  });

  it("formats pending age duration", () => {
    expect(formatDurationSeconds(null)).toBe("—");
    expect(formatDurationSeconds(45)).toBe("45 сек");
    expect(formatDurationSeconds(3600)).toBe("1 ч");
    expect(formatDurationSeconds(8100)).toBe("2 ч 15 мин");
  });

  it("detects coverage-only status reasons", () => {
    expect(isCoverageStatusReason("Telegram binding coverage is 66.67%")).toBe(true);
    expect(isCoverageStatusReason("3 pending telegram delivery row(s)")).toBe(false);
  });

  it("formats coverage labels", () => {
    expect(formatCoveragePercent(66.67)).toBe("66,7%");
    expect(formatBindingsCoverageLabel({ active_users: 9, users_with_telegram: 6, coverage_percent: 66.67 })).toBe(
      "6 из 9 пользователей (66,7%)",
    );
  });

  it("derives GREEN service status when only coverage triggers backend YELLOW", () => {
    const service = deriveTelegramServiceStatus(productionYellowSmokeFixture());
    expect(service.status).toBe("GREEN");
    expect(service.status_label).toBe("Работает");
    expect(service.operational_reasons).toEqual([]);
  });

  it("builds view for production YELLOW smoke fixture", () => {
    const view = buildTelegramStatusView(productionYellowSmokeFixture());
    expect(view.status).toBe("YELLOW");
    expect(view.status_label).toBe("Требует внимания");
    expect(view.service_status).toBe("GREEN");
    expect(view.service_status_label).toBe("Работает");
    expect(view.coverage_label).toBe("6 из 9 пользователей (66,7%)");
    expect(view.show_coverage_warning).toBe(true);
    expect(view.operational_reasons).toEqual([]);
    expect(view.unavailable_metric_ids).toContain("bot_service_active");
  });
});
