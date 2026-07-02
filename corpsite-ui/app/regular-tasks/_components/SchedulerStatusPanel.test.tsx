// FILE: corpsite-ui/app/regular-tasks/_components/SchedulerStatusPanel.test.tsx
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import SchedulerStatusPanel from "./SchedulerStatusPanel";
import * as api from "@/lib/api";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const STALE_STATUS: api.RegularTaskSchedulerStatus = {
  automatic_enabled: false,
  status: "needs_attention",
  status_label: "Требует внимания",
  status_explanation:
    "Последний запуск был успешным (22.06.2026 07:41), но с тех пор прошло 10 дн. — новых автоматических запусков не было (окно наблюдения: 8 дн.).",
  observation_window_days: 8,
  last_run_at: "2026-06-22T07:41:00+05:00",
  last_run_status: "ok",
  last_successful_run_at: "2026-06-22T07:41:00+05:00",
  last_result_label: "Успешно",
  last_error: null,
  expected_next_run_at: "2026-06-23T07:41:00+05:00",
  expected_next_run_label: "23.06.2026 07:41",
  is_cron_overdue: true,
  cron_overdue_days: 10,
  cron_interval_days: 1,
  hint: "Если автоматический запуск выключен или cron не настроен, новые регулярные задачи создаются только через догonяющий запуск.",
  recommended_action: {
    label: "Создать пропущенные задачи через догonяющий запуск",
    href: "/admin/regular-tasks/catch-up",
    kind: "catch_up",
  },
  checked_at: "2026-07-02T12:00:00+05:00",
  period_diagnostics: [
    {
      key: "past_week",
      preset: "past_week",
      schedule_type: "weekly",
      title: "Weekly",
      label: "24.06.2026–30.06.2026",
      period_display: "24.06.2026–30.06.2026",
      run_for_date: "2026-07-01",
      period_id: 100,
      period_start: "2026-06-24",
      period_end: "2026-06-30",
      active_templates_count: 3,
      tasks_count: 0,
      has_tasks: false,
      creation_status_label: "не создан",
      primary_reason: "После 22.06.2026 автоматический запуск не выполнялся.",
      likely_reasons: ["После 22.06.2026 автоматический запуск не выполнялся."],
    },
    {
      key: "monthly_reporting",
      preset: "manual",
      schedule_type: "monthly",
      title: "Monthly",
      label: "06.2026",
      period_display: "06.2026",
      run_for_date: "2026-07-01",
      period_id: 101,
      period_start: "2026-06-01",
      period_end: "2026-06-30",
      active_templates_count: 2,
      tasks_count: 0,
      has_tasks: false,
      creation_status_label: "не создан",
      primary_reason: "Не было автоматического запуска 01.07.2026.",
      likely_reasons: ["Не было автоматического запуска 01.07.2026."],
    },
  ],
};

describe("SchedulerStatusPanel", () => {
  it("renders status explanation and overdue cron expectation", async () => {
    vi.spyOn(api, "apiGetRegularTaskSchedulerStatus").mockResolvedValue(STALE_STATUS);

    render(<SchedulerStatusPanel variant="full" />);

    await waitFor(() => {
      expect(screen.getByTestId("scheduler-status-explanation")).toHaveTextContent("успешным");
    });

    expect(screen.getByTestId("scheduler-status-badge")).toHaveTextContent("Требует внимания");
    expect(screen.getByTestId("scheduler-last-result")).toHaveTextContent("Успешно");
    expect(screen.getByTestId("scheduler-next-run")).toHaveTextContent("23.06.2026 07:41");
    expect(screen.getByTestId("scheduler-overdue")).toHaveTextContent("10 дн.");
  });

  it("shows period diagnostics with primary reasons", async () => {
    vi.spyOn(api, "apiGetRegularTaskSchedulerStatus").mockResolvedValue(STALE_STATUS);

    render(<SchedulerStatusPanel variant="full" />);

    await waitFor(() => {
      expect(screen.getByTestId("scheduler-period-past_week")).toBeInTheDocument();
    });

    expect(screen.getByTestId("scheduler-period-reason-past_week")).toHaveTextContent(
      "После 22.06.2026",
    );
    expect(screen.getByTestId("scheduler-period-reason-monthly_reporting")).toHaveTextContent(
      "01.07.2026",
    );
  });

  it("shows recommended catch-up action", async () => {
    vi.spyOn(api, "apiGetRegularTaskSchedulerStatus").mockResolvedValue(STALE_STATUS);

    render(<SchedulerStatusPanel variant="full" />);

    await waitFor(() => {
      expect(screen.getByTestId("scheduler-recommended-action")).toBeInTheDocument();
    });

    expect(screen.getByTestId("scheduler-recommended-action")).toHaveTextContent("догonяющий запуск");
  });

  it("refreshes status on button click", async () => {
    const fetchMock = vi.spyOn(api, "apiGetRegularTaskSchedulerStatus").mockResolvedValue(STALE_STATUS);

    render(<SchedulerStatusPanel />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByTestId("scheduler-refresh-button"));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  });

  it("shows API error state", async () => {
    vi.spyOn(api, "apiGetRegularTaskSchedulerStatus").mockRejectedValue(new Error("403 Access denied"));

    render(<SchedulerStatusPanel />);

    await waitFor(() => {
      expect(screen.getByText("403 Access denied")).toBeInTheDocument();
    });
  });
});
