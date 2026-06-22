// FILE: corpsite-ui/app/regular-task-runs/_components/RegularTaskRunsJournalView.test.tsx
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  RegularTaskRunsJournalView,
  resolveItemsEmptyMessage,
} from "./RegularTaskRunsJournalView";
import type { RegularTaskRunItemRow, RegularTaskRunRow } from "@/lib/regularTaskRunJournal";

afterEach(cleanup);

const automaticRun: RegularTaskRunRow = {
  run_id: 12,
  started_at: "2026-06-17T10:15:00+05:00",
  finished_at: "2026-06-17T10:16:00+05:00",
  status: "ok",
  stats: {
    templates_total: 40,
    templates_due: 38,
    created: 30,
    deduped: 8,
    errors: 0,
    occurrence_date: "2026-06-17",
    run_kind: "automatic",
  },
};

const catchUpRun: RegularTaskRunRow = {
  run_id: 33,
  started_at: "2026-06-11T12:00:00+05:00",
  status: "partial",
  stats: {
    templates_total: 12,
    templates_due: 10,
    created: 5,
    deduped: 2,
    errors: 1,
    occurrence_date: "2026-06-11",
    run_kind: "catch_up",
    catch_up: {
      preset: "past_week",
      run_for_date: "2026-06-11",
      schedule_type: "weekly",
      org_group_id: 5,
      org_unit_id: 42,
    },
  },
};

const sampleItem: RegularTaskRunItemRow = {
  item_id: 101,
  run_id: 33,
  regular_task_id: 200,
  status: "ok",
  started_at: "2026-06-11T12:00:01+05:00",
  period_id: 77,
  executor_role_id: 3,
  executor_role_name: "Медсестра",
  is_due: true,
  created_tasks: 1,
  meta: {
    occurrence_date: "2026-06-11",
    run_kind: "catch_up",
    title_final: "Еженедельный отчёт",
    title_suffix: "09.06.2026–15.06.2026",
    task_id: 9001,
    origin_metadata_text:
      "---\nИсточник: Догоняющий запуск регулярной задачи\nID запуска: 33\nДата возникновения задачи: 2026-06-11\nТип запуска: догоняющий\nПериод: Прошлая неделя\n---",
  },
};

function renderView(overrides: Partial<React.ComponentProps<typeof RegularTaskRunsJournalView>> = {}) {
  const props = {
    runs: [catchUpRun, automaticRun],
    runsLoading: false,
    runsError: null,
    selectedRunId: 33,
    onSelectRun: vi.fn(),
    onRefreshRuns: vi.fn(),
    items: [sampleItem],
    itemsLoading: false,
    itemsError: null,
    onRefreshItems: vi.fn(),
    onlyIssues: false,
    onOnlyIssuesChange: vi.fn(),
    search: "",
    onSearchChange: vi.fn(),
    ...overrides,
  };
  render(<RegularTaskRunsJournalView {...props} />);
  return props;
}

describe("RegularTaskRunsJournalView", () => {
  it("renders page heading and subtitle", () => {
    renderView();
    const heading = screen.getByTestId("regular-task-runs-heading");
    expect(within(heading).getByRole("heading", { level: 1 })).toHaveTextContent(
      "Журнал запусков регулярных задач",
    );
    expect(within(heading).getByText(/История автоматических и догоняющих запусков регулярных задач\./)).toBeInTheDocument();
  });

  it("shows run list cards with type, dates and counts", () => {
    renderView({ selectedRunId: null, items: [] });
    const catchUpCard = screen.getByTestId("regular-task-run-card-33");
    expect(within(catchUpCard).getByText("Запуск №33")).toBeInTheDocument();
    expect(within(catchUpCard).getByText("Догоняющий")).toBeInTheDocument();
    expect(within(catchUpCard).getByText(/Создано: 5 · Дедуп: 2 · Ошибки: 1/)).toBeInTheDocument();
    expect(within(catchUpCard).getByText(/Дата возникновения задачи:/)).toBeInTheDocument();

    const autoCard = screen.getByTestId("regular-task-run-card-12");
    expect(within(autoCard).getByText("Автоматический")).toBeInTheDocument();
    expect(within(autoCard).getByText(/Создано: 30 · Дедуп: 8 · Ошибки: 0/)).toBeInTheDocument();
  });

  it("renders human-readable catch-up run summary", () => {
    renderView();
    const summary = screen.getByTestId("regular-task-run-summary");
    expect(within(summary).getByText("Догоняющий")).toBeInTheDocument();
    expect(within(summary).getByText("Еженедельно")).toBeInTheDocument();
    expect(within(summary).getByText("Прошлая неделя")).toBeInTheDocument();
    expect(within(summary).getByText("11.06.2026")).toBeInTheDocument();
    expect(within(summary).getByText("Шаблонов всего")).toBeInTheDocument();
    expect(within(summary).getByText("12")).toBeInTheDocument();
  });

  it("keeps raw JSON collapsed by default", () => {
    renderView();
    const details = screen.getByTestId("regular-task-run-json-details");
    expect(details).not.toHaveAttribute("open");
    expect(within(details).getByText("Технические детали (JSON)")).toBeInTheDocument();
  });

  it("renders scrollable item table for many items", () => {
    const manyItems: RegularTaskRunItemRow[] = Array.from({ length: 80 }, (_, i) => ({
      ...sampleItem,
      item_id: i + 1,
      regular_task_id: 200 + i,
      meta: {
        ...sampleItem.meta,
        task_id: 9000 + i,
        title_final: `Задача ${i + 1}`,
      },
    }));

    renderView({ items: manyItems });
    const scroll = screen.getByTestId("regular-task-run-items-scroll");
    expect(scroll.className).toMatch(/overflow-auto/);
    expect(scroll.className).toMatch(/max-h-/);
    expect(screen.getAllByTestId(/regular-task-run-item-/)).toHaveLength(80);
  });

  it("shows 'Ошибок нет.' when error filter hides all non-error items", () => {
    renderView({ onlyIssues: true, items: [sampleItem] });
    expect(screen.getByTestId("regular-task-run-items-empty")).toHaveTextContent("Ошибок нет.");
  });

  it("shows 'Элементы отсутствуют.' when run has no items", () => {
    renderView({ items: [] });
    expect(screen.getByTestId("regular-task-run-items-empty")).toHaveTextContent("Элементы отсутствуют.");
  });

  it("shows journal integrity warning for orphan runs", () => {
    renderView({
      runs: [
        {
          ...catchUpRun,
          item_count: 0,
          journal_warning:
            "Внимание: статистика запуска содержит результаты, но элементы журнала отсутствуют. Возможна неполная запись журнала.",
        },
      ],
      items: [],
    });
    expect(screen.getByTestId("regular-task-run-journal-warning")).toHaveTextContent(
      "Внимание: статистика запуска содержит результаты, но элементы журнала отсутствуют.",
    );
  });

  it("selects run from list", () => {
    const onSelectRun = vi.fn();
    renderView({ selectedRunId: null, items: [], onSelectRun });
    fireEvent.click(screen.getByTestId("regular-task-run-card-12"));
    expect(onSelectRun).toHaveBeenCalledWith(12);
  });
});

describe("resolveItemsEmptyMessage", () => {
  it("returns filter-specific messages", () => {
    expect(resolveItemsEmptyMessage([], [], false, "")).toBe("Элементы отсутствуют.");
    expect(resolveItemsEmptyMessage([sampleItem], [], true, "")).toBe("Ошибок нет.");
  });
});
