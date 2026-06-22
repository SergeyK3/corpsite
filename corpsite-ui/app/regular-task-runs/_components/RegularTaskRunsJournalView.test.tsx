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
  item_count: 1,
  stats: {
    templates_total: 12,
    templates_due: 10,
    created: 5,
    deduped: 2,
    errors: 1,
    item_count: 1,
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
  executor_role_name: "Госпитальный эксперт",
  is_due: true,
  created_tasks: 1,
  meta: {
    occurrence_date: "2026-06-11",
    run_kind: "catch_up",
    task_title: "Госпитальный эксперт",
    title_final: "Госпитальный эксперт",
    due_date: "2026-06-24",
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
          stats: {
            ...catchUpRun.stats,
            item_count: 0,
          },
          journal_warning:
            "Внимание: статистика запуска содержит результаты, но элементы журнала отсутствуют. Возможна неполная запись журнала.",
        },
      ],
      items: [],
    });
    expect(screen.getByTestId("regular-task-run-journal-warning")).toHaveTextContent(
      "Внимание: статистика запуска содержит результаты, но элементы журнала отсутствуют.",
    );
    expect(screen.getByTestId("regular-task-run-task-list-unavailable")).toHaveTextContent(
      "Список задач недоступен: элементы журнала отсутствуют.",
    );
    expect(screen.queryByTestId("regular-task-run-task-list-expected-not-loaded")).not.toBeInTheDocument();
  });

  it("shows loading state for task list while items are loading", () => {
    renderView({
      runs: [{ ...catchUpRun, item_count: 2, stats: { ...catchUpRun.stats, item_count: 2 } }],
      items: [],
      itemsLoading: true,
    });
    expect(screen.getByText("Загрузка списка задач…")).toBeInTheDocument();
    expect(screen.queryByTestId("regular-task-run-task-list-unavailable")).not.toBeInTheDocument();
    expect(screen.queryByTestId("regular-task-run-task-list-expected-not-loaded")).not.toBeInTheDocument();
  });

  it("shows diagnostic message when item_count > 0 but items are empty", () => {
    renderView({
      runs: [{ ...catchUpRun, item_count: 2, stats: { ...catchUpRun.stats, item_count: 2, deduped: 2, created: 0 } }],
      items: [],
      itemsLoading: false,
      itemsError: null,
    });
    expect(screen.getByTestId("regular-task-run-task-list-expected-not-loaded")).toHaveTextContent(
      "Элементы журнала ожидаются, но не загружены.",
    );
    expect(screen.queryByTestId("regular-task-run-task-list-unavailable")).not.toBeInTheDocument();
    expect(screen.queryByTestId("regular-task-run-task-list-load-error")).not.toBeInTheDocument();
  });

  it("shows API load error in task list when itemsError is set", () => {
    renderView({
      runs: [{ ...catchUpRun, item_count: 2, stats: { ...catchUpRun.stats, item_count: 2, deduped: 2, created: 0 } }],
      items: [],
      itemsLoading: false,
      itemsError: "Access denied",
    });
    expect(screen.getByTestId("regular-task-run-task-list-load-error")).toHaveTextContent(
      "Не удалось загрузить элементы журнала: Access denied",
    );
    expect(screen.queryByTestId("regular-task-run-task-list-expected-not-loaded")).not.toBeInTheDocument();
  });

  it("does not show previous run task rows after switching runs", () => {
    const props = {
      runs: [catchUpRun, automaticRun],
      runsLoading: false,
      runsError: null,
      selectedRunId: 33,
      onSelectRun: vi.fn(),
      onRefreshRuns: vi.fn(),
      items: [sampleItem] as RegularTaskRunItemRow[],
      itemsLoading: false,
      itemsError: null,
      onRefreshItems: vi.fn(),
      onlyIssues: false,
      onOnlyIssuesChange: vi.fn(),
      search: "",
      onSearchChange: vi.fn(),
    };

    const { rerender } = render(<RegularTaskRunsJournalView {...props} />);
    expect(screen.getByTestId("regular-task-run-task-row-101")).toBeInTheDocument();

    rerender(
      <RegularTaskRunsJournalView
        {...props}
        selectedRunId={12}
        items={[]}
        itemsLoading={true}
        itemsError={null}
      />,
    );

    expect(screen.queryByTestId("regular-task-run-task-row-101")).not.toBeInTheDocument();
    expect(screen.getByText("Загрузка списка задач…")).toBeInTheDocument();
  });

  it("renders two dedup task rows when item_count=2 and items are loaded", () => {
    const dedupItem = (itemId: number, taskId: number): RegularTaskRunItemRow => ({
      item_id: itemId,
      run_id: 33,
      regular_task_id: 200 + itemId,
      status: "ok",
      started_at: "2026-06-11T12:00:01+05:00",
      executor_role_name: "Госпитальный эксперт",
      is_due: true,
      created_tasks: 0,
      meta: {
        deduped: true,
        task_title: `Задача ${itemId}`,
        due_date: "2026-06-24",
        task_id: taskId,
      },
    });

    renderView({
      runs: [{ ...catchUpRun, item_count: 2, stats: { ...catchUpRun.stats, item_count: 2, deduped: 2, created: 0 } }],
      items: [dedupItem(201, 9101), dedupItem(202, 9102)],
    });

    expect(screen.getByTestId("regular-task-run-task-row-201")).toBeInTheDocument();
    expect(screen.getByTestId("regular-task-run-task-row-202")).toBeInTheDocument();
    expect(screen.getAllByText("уже существовала")).toHaveLength(2);
    expect(screen.getByTestId("regular-task-run-task-open-201")).toHaveAttribute(
      "href",
      "/tasks?task_id=9101&return_to=%2Fregular-task-runs%3Frun_id%3D33",
    );
  });

  it("shows run mode badge when dry_run is available in stats", () => {
    renderView({
      runs: [
        {
          ...catchUpRun,
          stats: { ...catchUpRun.stats, dry_run: true },
        },
      ],
      items: [],
    });
    expect(screen.getByTestId("regular-task-run-mode-33")).toHaveTextContent("Пробный прогон");
    expect(screen.getByTestId("regular-task-run-summary-mode")).toHaveTextContent("Пробный прогон");
  });

  it("shows live run mode from loaded dedup items", () => {
    const dedupOnlyItem: RegularTaskRunItemRow = {
      ...sampleItem,
      created_tasks: 0,
      meta: { ...sampleItem.meta, deduped: true, task_id: 9001 },
    };
    renderView({ items: [dedupOnlyItem] });
    expect(screen.getByTestId("regular-task-run-mode-33")).toHaveTextContent("Боевой прогон");
    expect(screen.getByTestId("regular-task-run-summary-mode")).toHaveTextContent("Боевой прогон");
  });

  it("renders human-readable task list row from run item meta", () => {
    renderView({ items: [sampleItem] });
    const row = screen.getByTestId("regular-task-run-task-row-101");
    const cells = within(row).getAllByRole("cell");
    expect(cells[0]).toHaveTextContent("Госпитальный эксперт");
    expect(cells[1]).toHaveTextContent("Госпитальный эксперт");
    expect(cells[2]).toHaveTextContent("24.06.2026");
    expect(cells[3]).toHaveTextContent("создана");
    const link = screen.getByTestId("regular-task-run-task-open-101");
    expect(link).toHaveTextContent("Открыть");
    expect(link).toHaveAttribute(
      "href",
      "/tasks?task_id=9001&return_to=%2Fregular-task-runs%3Frun_id%3D33",
    );
  });

  it("builds open link with return_to for the selected run", () => {
    renderView({
      selectedRunId: 33,
      items: [sampleItem],
    });
    expect(screen.getByTestId("regular-task-run-task-open-101")).toHaveAttribute(
      "href",
      "/tasks?task_id=9001&return_to=%2Fregular-task-runs%3Frun_id%3D33",
    );
  });

  it("does not render open link when task_id is missing", () => {
    const errorItem: RegularTaskRunItemRow = {
      ...sampleItem,
      item_id: 102,
      status: "error",
      created_tasks: 0,
      error: "executor_role_id is required",
      meta: {
        task_title: "Ошибочная задача",
        due_date: "2026-06-24",
      },
    };
    renderView({ items: [errorItem] });
    expect(screen.queryByTestId("regular-task-run-task-open-102")).not.toBeInTheDocument();
    expect(screen.getByTestId("regular-task-run-task-open-unavailable-102")).toHaveTextContent("—");
  });

  it("keeps JSON details below the task list and items sections", () => {
    renderView({ items: [sampleItem] });
    const taskList = screen.getByTestId("regular-task-run-task-list");
    const itemsSection = screen.getByTestId("regular-task-run-items-section");
    const jsonDetails = screen.getByTestId("regular-task-run-json-details");
    expect(taskList.compareDocumentPosition(itemsSection) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(itemsSection.compareDocumentPosition(jsonDetails) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
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
