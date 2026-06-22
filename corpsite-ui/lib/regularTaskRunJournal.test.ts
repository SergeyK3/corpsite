// FILE: corpsite-ui/lib/regularTaskRunJournal.test.ts
import { describe, expect, it } from "vitest";

import {
  buildItemOriginView,
  buildRunListEntry,
  buildRunSummary,
  buildRunTaskListRows,
  fmtDate,
  formatRunTaskListLoadError,
  itemOutcomeLabel,
  parseOriginMetadataText,
  resolveOccurrenceDate,
  resolveRunMode,
  resolveRunTaskListState,
  runModeLabel,
  runTaskOutcomeLabel,
  type RegularTaskRunItemRow,
  type RegularTaskRunRow,
} from "./regularTaskRunJournal";

describe("parseOriginMetadataText", () => {
  it("extracts occurrence date from origin block", () => {
    const block = `
---
Источник: Автоматический запуск регулярной задачи
ID запуска: 10
Дата возникновения задачи: 2026-06-17
Тип запуска: автоматический
---`;
    const parsed = parseOriginMetadataText(block);
    expect(parsed.occurrence_date).toBe("2026-06-17");
    expect(parsed.run_kind).toBe("автоматический");
    expect(parsed.run_id).toBe("10");
  });

  it("ignores placeholder ellipsis values", () => {
    const parsed = parseOriginMetadataText("Дата возникновения задачи: ...");
    expect(parsed.occurrence_date).toBeUndefined();
  });
});

describe("buildRunListEntry", () => {
  it("builds compact card labels from run stats", () => {
    const run: RegularTaskRunRow = {
      run_id: 33,
      started_at: "2026-06-11T12:00:00+05:00",
      status: "ok",
      stats: {
        created: 5,
        deduped: 2,
        errors: 1,
        occurrence_date: "2026-06-11",
        run_kind: "catch_up",
        catch_up: { preset: "past_week", run_for_date: "2026-06-11" },
      },
    };
    const entry = buildRunListEntry(run);
    expect(entry.run_kind_label).toBe("Догоняющий");
    expect(entry.counts_label).toBe("Создано: 5 · Дедуп: 2 · Ошибки: 1");
    expect(entry.occurrence_date_label).toBe(fmtDate("2026-06-11"));
  });
});

describe("itemOutcomeLabel", () => {
  it("maps item states to operator labels", () => {
    const created: RegularTaskRunItemRow = {
      item_id: 1,
      run_id: 1,
      regular_task_id: 1,
      status: "ok",
      started_at: "2026-06-01",
      is_due: true,
      created_tasks: 1,
    };
    const dedup: RegularTaskRunItemRow = {
      ...created,
      item_id: 2,
      created_tasks: 0,
      meta: { deduped: true },
    };
    expect(itemOutcomeLabel(created)).toBe("Создано");
    expect(itemOutcomeLabel(dedup)).toBe("Дедуп");
  });
});

describe("buildRunSummary", () => {
  const automaticRun: RegularTaskRunRow = {
    run_id: 12,
    started_at: "2026-06-17T10:00:00+05:00",
    status: "ok",
    stats: {
      created: 3,
      deduped: 1,
      errors: 0,
      occurrence_date: "2026-06-17",
      run_kind: "automatic",
    },
  };

  it("uses structured stats fields for occurrence date", () => {
    const summary = buildRunSummary(automaticRun, []);
    expect(summary.occurrence_date).toBe("2026-06-17");
    expect(summary.occurrence_date_label).toBe(fmtDate("2026-06-17"));
    expect(summary.run_kind_label).toBe("Автоматический");
    expect(summary.created).toBe(3);
    expect(summary.deduped).toBe(1);
  });

  it("derives catch-up summary from stats.catch_up", () => {
    const run: RegularTaskRunRow = {
      run_id: 33,
      started_at: "2026-06-17T12:00:00+05:00",
      status: "ok",
      stats: {
        created: 2,
        deduped: 0,
        errors: 0,
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
    const summary = buildRunSummary(run, []);
    expect(summary.run_kind_label).toBe("Догоняющий");
    expect(summary.period_label).toBe("Прошлая неделя");
    expect(summary.schedule_type_label).toBe("Еженедельно");
    expect(summary.org_scope_label).toContain("#42");
    expect(summary.org_scope_label).toContain("#5");
  });

  it("falls back to item meta when stats lack occurrence_date", () => {
    const run: RegularTaskRunRow = {
      run_id: 7,
      started_at: "2026-06-01T08:00:00+05:00",
      status: "ok",
      stats: { created: 1, deduped: 0, errors: 0 },
    };
    const items: RegularTaskRunItemRow[] = [
      {
        item_id: 1,
        run_id: 7,
        regular_task_id: 100,
        status: "ok",
        started_at: "2026-06-01T08:00:01+05:00",
        is_due: true,
        created_tasks: 1,
        meta: {
          today_effective: "2026-06-01",
          origin_metadata_text:
            "---\nДата возникновения задачи: 2026-06-01\nТип запуска: автоматический\n---",
        },
      },
    ];
    expect(resolveOccurrenceDate(run.stats, items)).toBe("2026-06-01");
    const summary = buildRunSummary(run, items);
    expect(summary.occurrence_date).toBe("2026-06-01");
  });
});

describe("buildRunTaskListRows", () => {
  const item: RegularTaskRunItemRow = {
    item_id: 5,
    run_id: 1,
    regular_task_id: 100,
    status: "ok",
    started_at: "2026-06-01",
    executor_role_id: 2,
    executor_role_name: "Амбулаторный эксперт",
    is_due: true,
    created_tasks: 0,
    meta: {
      task_title: "Амбулаторный эксперт",
      due_date: "2026-06-24",
      deduped: true,
    },
  };

  it("builds operator-facing row labels from item meta", () => {
    const [row] = buildRunTaskListRows([{ ...item, meta: { ...item.meta, task_id: 9001 } }]);
    expect(row.task_title).toBe("Амбулаторный эксперт");
    expect(row.executor_label).toBe("Амбулаторный эксперт");
    expect(row.deadline_label).toBe(fmtDate("2026-06-24"));
    expect(row.outcome_label).toBe("уже существовала");
    expect(row.task_id).toBe(9001);
    expect(row.task_href).toBe("/tasks?task_id=9001");
    expect(runTaskOutcomeLabel(item)).toBe("уже существовала");
  });

  it("returns unavailable state for orphan runs without items", () => {
    const run: RegularTaskRunRow = {
      run_id: 9,
      started_at: "2026-06-01",
      status: "partial",
      stats: { templates_due: 2, created: 1, deduped: 1, errors: 0 },
      item_count: 0,
      journal_warning: "warning",
    };
    const summary = buildRunSummary(run, []);
    expect(resolveRunTaskListState(run, summary, [], false)).toEqual({ kind: "unavailable" });
  });

  it("returns expected_not_loaded when item_count > 0 but items are empty", () => {
    const run: RegularTaskRunRow = {
      run_id: 39,
      started_at: "2026-06-01",
      status: "ok",
      stats: { templates_due: 2, created: 0, deduped: 2, errors: 0, item_count: 2 },
      item_count: 2,
    };
    const summary = buildRunSummary(run, []);
    expect(resolveRunTaskListState(run, summary, [], false, null)).toEqual({ kind: "expected_not_loaded" });
  });

  it("returns load_error when items request failed", () => {
    const run: RegularTaskRunRow = {
      run_id: 39,
      started_at: "2026-06-01",
      status: "ok",
      stats: { templates_due: 2, created: 0, deduped: 2, errors: 0, item_count: 2 },
      item_count: 2,
    };
    const summary = buildRunSummary(run, []);
    expect(resolveRunTaskListState(run, summary, [], false, "Access denied")).toEqual({
      kind: "load_error",
      message: formatRunTaskListLoadError("Access denied"),
    });
  });

  it("returns loading while items are still fetching", () => {
    const run: RegularTaskRunRow = {
      run_id: 39,
      started_at: "2026-06-01",
      status: "ok",
      stats: { templates_due: 2, created: 0, deduped: 2, errors: 0, item_count: 2 },
      item_count: 2,
    };
    const summary = buildRunSummary(run, []);
    expect(resolveRunTaskListState(run, summary, [], true)).toEqual({ kind: "loading" });
  });

  it("returns rows for loaded dedup items", () => {
    const run: RegularTaskRunRow = {
      run_id: 39,
      started_at: "2026-06-01",
      status: "ok",
      stats: { templates_due: 2, created: 0, deduped: 2, errors: 0, item_count: 2 },
      item_count: 2,
    };
    const items: RegularTaskRunItemRow[] = [
      {
        item_id: 1,
        run_id: 39,
        regular_task_id: 100,
        status: "ok",
        started_at: "2026-06-01",
        is_due: true,
        created_tasks: 0,
        meta: { deduped: true, task_title: "Задача 1", task_id: 9001 },
      },
      {
        item_id: 2,
        run_id: 39,
        regular_task_id: 101,
        status: "ok",
        started_at: "2026-06-01",
        is_due: true,
        created_tasks: 0,
        meta: { deduped: true, task_title: "Задача 2", task_id: 9002 },
      },
    ];
    const summary = buildRunSummary(run, items);
    const state = resolveRunTaskListState(run, summary, items, false);
    expect(state.kind).toBe("rows");
    if (state.kind === "rows") {
      expect(state.rows).toHaveLength(2);
      expect(state.rows[0].outcome_label).toBe("уже существовала");
      expect(state.rows[0].task_href).toBe("/tasks?task_id=9001");
    }
  });
});

describe("resolveRunMode", () => {
  it("reads dry_run from run stats when present", () => {
    expect(resolveRunMode({ dry_run: true }, [])).toBe("dry");
    expect(runModeLabel("dry")).toBe("Пробный прогон");
    expect(resolveRunMode({ dry_run: false }, [])).toBe("live");
    expect(runModeLabel("live")).toBe("Боевой прогон");
  });

  it("derives dry run from item meta when stats lack the flag", () => {
    const items: RegularTaskRunItemRow[] = [
      {
        item_id: 1,
        run_id: 1,
        regular_task_id: 1,
        status: "skip",
        started_at: "2026-06-01",
        is_due: true,
        created_tasks: 0,
        meta: { reason: "dry_run", dry_run: true },
      },
    ];
    expect(resolveRunMode({}, items)).toBe("dry");
  });

  it("derives live run from dedup or created items", () => {
    const items: RegularTaskRunItemRow[] = [
      {
        item_id: 1,
        run_id: 1,
        regular_task_id: 1,
        status: "ok",
        started_at: "2026-06-01",
        is_due: true,
        created_tasks: 0,
        meta: { deduped: true, task_id: 42 },
      },
    ];
    expect(resolveRunMode({}, items)).toBe("live");
  });
});

describe("buildItemOriginView", () => {
  it("shows formatted occurrence date instead of ellipsis", () => {
    const item: RegularTaskRunItemRow = {
      item_id: 5,
      run_id: 10,
      regular_task_id: 200,
      status: "ok",
      started_at: "2026-06-17T10:00:00+05:00",
      is_due: true,
      created_tasks: 1,
      meta: {
        occurrence_date: "2026-06-17",
        run_kind: "automatic",
        origin_metadata_text:
          "---\nДата возникновения задачи: 2026-06-17\nТип запуска: автоматический\n---",
      },
    };
    const view = buildItemOriginView(item);
    expect(view.occurrence_date).toBe("2026-06-17");
    expect(view.occurrence_date_label).not.toBe("...");
    expect(view.occurrence_date_label).toBe(fmtDate("2026-06-17"));
  });
});
