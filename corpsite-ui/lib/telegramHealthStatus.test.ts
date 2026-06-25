// FILE: corpsite-ui/lib/telegramHealthStatus.test.ts

import { describe, expect, it } from "vitest";

import {
  buildTelegramStatusView,
  formatConfiguredLabel,
  formatDurationSeconds,
  productionYellowSmokeFixture,
  telegramHealthStatusLabel,
} from "./telegramHealthStatus";

describe("telegramHealthStatus", () => {
  it("maps health status labels", () => {
    expect(telegramHealthStatusLabel("GREEN")).toBe("Работает");
    expect(telegramHealthStatusLabel("YELLOW")).toBe("Требует внимания");
    expect(telegramHealthStatusLabel("RED")).toBe("Не работает");
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

  it("builds view for production YELLOW smoke fixture", () => {
    const view = buildTelegramStatusView(productionYellowSmokeFixture());
    expect(view.status).toBe("YELLOW");
    expect(view.status_label).toBe("Требует внимания");
    expect(view.show_coverage_warning).toBe(true);
    expect(view.unavailable_metric_ids).toContain("bot_service_active");
  });
});
