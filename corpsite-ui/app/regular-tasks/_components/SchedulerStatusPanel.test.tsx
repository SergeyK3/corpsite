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
  it("shows summary facts before detailed explanation and highlights overdue", async () => {
    vi.spyOn(api, "apiGetRegularTaskSchedulerStatus").mockResolvedValue(STALE_STATUS);

    render(<SchedulerStatusPanel variant="full" />);

    await waitFor(() => {
      expect(screen.getByTestId("scheduler-summary-block")).toBeInTheDocument();
    });

    expect(screen.getByTestId("scheduler-status-badge")).toHaveTextContent("Требует внимания");
    expect(screen.getByTestId("scheduler-last-run")).toHaveTextContent("22.06.2026");
    expect(screen.getByTestId("scheduler-last-success")).toHaveTextContent("22.06.2026");
    expect(screen.getByTestId("scheduler-next-run")).toHaveTextContent("23.06.2026 07:41");
    expect(screen.getByTestId("scheduler-overdue-badge")).toHaveTextContent("10 дней");
    expect(screen.getByTestId("scheduler-last-result")).toHaveTextContent("Успешно");

    const summary = screen.getByTestId("scheduler-summary-block");
    const explanation = screen.getByTestId("scheduler-status-explanation");
    expect(summary.compareDocumentPosition(explanation) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("shows recommended action before period diagnostics", async () => {
    vi.spyOn(api, "apiGetRegularTaskSchedulerStatus").mockResolvedValue(STALE_STATUS);

    render(<SchedulerStatusPanel variant="full" />);

    await waitFor(() => {
      expect(screen.getByTestId("scheduler-recommended-action")).toBeInTheDocument();
    });

    const action = screen.getByTestId("scheduler-recommended-action");
    const diagnostics = screen.getByTestId("scheduler-period-diagnostics");
    expect(action.compareDocumentPosition(diagnostics) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(action).toHaveTextContent("догonяющий запуск");
  });

  it("shows aggregated missed-period summary before diagnostic cards", async () => {
    vi.spyOn(api, "apiGetRegularTaskSchedulerStatus").mockResolvedValue(STALE_STATUS);

    render(<SchedulerStatusPanel variant="full" />);

    await waitFor(() => {
      expect(screen.getByTestId("scheduler-period-summary")).toBeInTheDocument();
    });

    expect(screen.getByTestId("scheduler-period-summary")).toHaveTextContent("Пропущено периодов: 2");
    expect(screen.getByTestId("scheduler-period-summary-item-past_week")).toHaveTextContent(
      "Weekly — 24.06.2026–30.06.2026",
    );
    expect(screen.getByTestId("scheduler-period-summary-item-monthly_reporting")).toHaveTextContent(
      "Monthly — 06.2026",
    );

    const summary = screen.getByTestId("scheduler-period-summary");
    const firstCard = screen.getByTestId("scheduler-period-past_week");
    expect(summary.compareDocumentPosition(firstCard) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("shows all-clear summary when every period has tasks", async () => {
    vi.spyOn(api, "apiGetRegularTaskSchedulerStatus").mockResolvedValue({
      ...STALE_STATUS,
      period_diagnostics: STALE_STATUS.period_diagnostics!.map((row) => ({
        ...row,
        has_tasks: true,
        creation_status_label: "создан",
      })),
    });

    render(<SchedulerStatusPanel variant="full" />);

    await waitFor(() => {
      expect(screen.getByTestId("scheduler-period-summary")).toHaveTextContent(
        "✓ Пропущенных периодов не обнаружено",
      );
    });

    expect(screen.getByTestId("scheduler-period-past_week")).toBeInTheDocument();
    expect(screen.getByTestId("scheduler-period-monthly_reporting")).toBeInTheDocument();
  });

  it("shows all-clear summary when period diagnostics array is empty", async () => {
    vi.spyOn(api, "apiGetRegularTaskSchedulerStatus").mockResolvedValue({
      ...STALE_STATUS,
      period_diagnostics: [],
    });

    render(<SchedulerStatusPanel variant="full" />);

    await waitFor(() => {
      expect(screen.getByTestId("scheduler-period-summary")).toHaveTextContent(
        "✓ Пропущенных периодов не обнаружено",
      );
    });

    expect(screen.queryByTestId("scheduler-period-past_week")).not.toBeInTheDocument();
  });

  it("shows compact period diagnostics with factual reason labels", async () => {
    vi.spyOn(api, "apiGetRegularTaskSchedulerStatus").mockResolvedValue(STALE_STATUS);

    render(<SchedulerStatusPanel variant="full" />);

    await waitFor(() => {
      expect(screen.getByTestId("scheduler-period-past_week")).toBeInTheDocument();
    });

    expect(screen.getByTestId("scheduler-period-status-past_week")).toHaveTextContent("✖ Не создан");
    expect(screen.getByTestId("scheduler-period-reason-past_week")).toHaveTextContent(
      "После 22.06.2026",
    );
    expect(screen.getByTestId("scheduler-period-status-monthly_reporting")).toHaveTextContent("✖ Не создан");
    expect(screen.getByTestId("scheduler-period-reason-monthly_reporting")).toHaveTextContent(
      "01.07.2026",
    );
    expect(screen.queryByText("Вероятная причина:")).not.toBeInTheDocument();
  });

  it("documents why manual scheduler run is not offered in this panel", async () => {
    vi.spyOn(api, "apiGetRegularTaskSchedulerStatus").mockResolvedValue(STALE_STATUS);

    render(<SchedulerStatusPanel variant="full" />);

    await waitFor(() => {
      expect(screen.getByTestId("scheduler-manual-run-note")).toBeInTheDocument();
    });

    expect(screen.getByTestId("scheduler-manual-run-note")).toHaveTextContent(
      "POST /internal/regular-tasks/run",
    );
    expect(screen.getByTestId("scheduler-manual-run-note")).toHaveTextContent("пропущенные отчётные периоды");
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
