// FILE: corpsite-ui/app/admin/system/_components/TelegramStatusPanel.test.tsx
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import TelegramStatusPanel, { TelegramStatusPanelBodyForTests } from "./TelegramStatusPanel";
import { fetchTelegramHealth } from "../_lib/adminSystemApi.client";
import { productionYellowSmokeFixture } from "@/lib/telegramHealthStatus";

vi.mock("../_lib/adminSystemApi.client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../_lib/adminSystemApi.client")>();
  return {
    ...actual,
    fetchTelegramHealth: vi.fn(),
  };
});

const mockedFetch = vi.mocked(fetchTelegramHealth);

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.useRealTimers();
});

describe("TelegramStatusPanelBodyForTests", () => {
  it("renders production-like YELLOW state with service GREEN and separate coverage warning", () => {
    render(<TelegramStatusPanelBodyForTests data={productionYellowSmokeFixture()} refreshIntervalMs={45_000} />);

    expect(screen.getByTestId("telegram-status-badge")).toHaveTextContent("Работает");
    expect(screen.queryByTestId("telegram-status-reasons")).not.toBeInTheDocument();
    expect(screen.getByTestId("telegram-last-sent")).toHaveTextContent("Последняя успешная отправка");
    expect(screen.getByTestId("telegram-chip-pending")).toHaveTextContent("Pending: 0");
    expect(screen.getByTestId("telegram-chip-sent")).toHaveTextContent("Sent 24h: 16");
    expect(screen.getByTestId("telegram-chip-failed")).toHaveTextContent("Failed 24h: 0");
    expect(screen.getByTestId("telegram-bindings-coverage")).toHaveTextContent(
      "6 из 9 пользователей (66,7%)",
    );
    expect(screen.getByTestId("telegram-coverage-warning")).toHaveTextContent(
      "Не у всех активных пользователей привязан Telegram.",
    );
    expect(screen.getByTestId("telegram-all-status-reasons")).toHaveTextContent("66.67%");
    expect(screen.getByTestId("telegram-config-bot-token")).toHaveTextContent("✓ BOT_TOKEN");
    expect(screen.getByTestId("telegram-auto-refresh")).toHaveTextContent("Автообновление: 45 сек");
    expect(screen.queryByTestId("telegram-chip-oldest-pending")).not.toBeInTheDocument();
  });

  it("renders RED state", () => {
    const data = {
      ...productionYellowSmokeFixture(),
      status: "RED" as const,
      status_reasons: ["BOT_TOKEN is not configured"],
      bot_configuration: {
        ...productionYellowSmokeFixture().bot_configuration,
        bot_token_present: false,
      },
    };
    render(<TelegramStatusPanelBodyForTests data={data} refreshIntervalMs={45_000} />);
    expect(screen.getByTestId("telegram-status-badge")).toHaveTextContent("Не работает");
    expect(screen.getByTestId("telegram-config-bot-token")).toHaveTextContent("✗ BOT_TOKEN");
  });

  it("renders GREEN state", () => {
    const data = {
      ...productionYellowSmokeFixture(),
      status: "GREEN" as const,
      status_reasons: ["Queue empty"],
      bindings: {
        active_users: 6,
        users_with_telegram: 6,
        coverage_percent: 100,
      },
    };
    render(<TelegramStatusPanelBodyForTests data={data} refreshIntervalMs={45_000} />);
    expect(screen.getByTestId("telegram-status-badge")).toHaveTextContent("Работает");
    expect(screen.queryByTestId("telegram-coverage-warning")).not.toBeInTheDocument();
  });

  it("renders operational YELLOW service status when queue has pending rows", () => {
    const data = {
      ...productionYellowSmokeFixture(),
      status: "YELLOW" as const,
      status_reasons: ["3 pending telegram delivery row(s)", "Telegram binding coverage is 66.67%"],
      queue: {
        ...productionYellowSmokeFixture().queue,
        pending_count: 3,
        oldest_pending_age_sec: 120,
        oldest_pending_at: "2026-06-25T10:00:00+00:00",
      },
    };
    render(<TelegramStatusPanelBodyForTests data={data} refreshIntervalMs={45_000} />);
    expect(screen.getByTestId("telegram-status-badge")).toHaveTextContent("Есть предупреждения");
    expect(screen.getByTestId("telegram-status-reasons")).toHaveTextContent("3 pending telegram delivery row(s)");
  });

  it("does not render secret token values", () => {
    render(<TelegramStatusPanelBodyForTests data={productionYellowSmokeFixture()} refreshIntervalMs={45_000} />);
    const text = document.body.textContent ?? "";
    expect(text).not.toMatch(/8123456789:/);
    expect(text).not.toContain("AAHabcdefghijklmnopqrstuvwxyz");
    expect(text).not.toContain("INTERNAL_API_TOKEN=");
    expect(text).not.toContain("BOT_TOKEN=");
  });
});

describe("TelegramStatusPanel", () => {
  it("shows loading then data", async () => {
    mockedFetch.mockResolvedValueOnce(productionYellowSmokeFixture());

    render(<TelegramStatusPanel refreshIntervalMs={60_000} />);

    expect(screen.getByTestId("telegram-loading")).toHaveTextContent("Загрузка статуса Telegram…");

    await waitFor(() => {
      expect(screen.getByTestId("telegram-status-badge")).toHaveTextContent("Работает");
    });
    expect(screen.getByTestId("telegram-auto-refresh")).toHaveTextContent("Автообновление: 60 сек");
  });

  it("shows 403 error state", async () => {
    mockedFetch.mockRejectedValueOnce({ status: 403, message: "Forbidden" });

    render(<TelegramStatusPanel refreshIntervalMs={60_000} />);

    await waitFor(() => {
      expect(screen.getByTestId("telegram-error")).toHaveTextContent(
        "Недостаточно прав для просмотра статуса Telegram",
      );
    });
  });
});
