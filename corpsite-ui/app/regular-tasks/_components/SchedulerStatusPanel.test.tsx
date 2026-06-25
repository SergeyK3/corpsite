// FILE: corpsite-ui/app/regular-tasks/_components/SchedulerStatusPanel.test.tsx
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import SchedulerStatusPanel from "./SchedulerStatusPanel";
import type { RegularTaskRunRow } from "@/lib/regularTaskRunJournal";

afterEach(cleanup);

describe("SchedulerStatusPanel", () => {
  it("renders working state for a recent successful automatic run", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-25T12:00:00+05:00"));

    const runs: RegularTaskRunRow[] = [
      {
        run_id: 1,
        started_at: "2026-06-25T10:00:00+05:00",
        status: "ok",
        stats: {
          run_kind: "automatic",
          dry_run: false,
          errors: 0,
        },
      },
    ];

    render(<SchedulerStatusPanel runs={runs} />);

    expect(screen.getByTestId("scheduler-status-panel")).toBeInTheDocument();
    expect(screen.getByTestId("scheduler-status-badge")).toHaveTextContent("Работает");
    expect(screen.getByTestId("scheduler-last-result")).toHaveTextContent("Успешно");
    expect(screen.getByTestId("scheduler-journal-link")).toHaveAttribute("href", "/regular-task-runs");

    vi.useRealTimers();
  });

  it("shows loading state", () => {
    render(<SchedulerStatusPanel runs={[]} loading />);
    expect(screen.getByText("Загрузка состояния…")).toBeInTheDocument();
  });

  it("shows error state", () => {
    render(<SchedulerStatusPanel runs={[]} error="Не удалось загрузить историю запусков." />);
    expect(screen.getByText("Не удалось загрузить историю запусков.")).toBeInTheDocument();
  });
});
