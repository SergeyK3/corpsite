// FILE: corpsite-ui/lib/catchUpWorkflow.test.ts

import { describe, expect, it } from "vitest";

import type { CatchUpRegularTasksParams } from "./api";
import {
  buildCatchUpPayload,
  buildCatchUpReviewRow,
  formatReportingPeriodRange,
  pastWeekPresetHint,
  payloadsEquivalent,
  resolveAggregatePeriodFromItems,
  resolveDefaultScheduleType,
  validateCatchUpForm,
} from "./catchUpWorkflow";
import type { RegularTaskRunItemRow } from "./regularTaskRunJournal";

const sampleItem: RegularTaskRunItemRow = {
  item_id: 1,
  run_id: 40,
  regular_task_id: 1,
  status: "skip",
  started_at: "2026-06-22T12:00:00",
  executor_role_id: 3,
  executor_role_name: "Госпитальный эксперт",
  is_due: true,
  created_tasks: 0,
  meta: {
    template_title: "QM weekly",
    report_code: "QM_WEEKLY",
    period_start: "2026-06-17",
    period_end: "2026-06-23",
    due_date: "2026-06-23",
    occurrence_date: "2026-06-24",
    title_final: "QM weekly → Госпитальный эксперт (17.06.2026–23.06.2026)",
    reason: "dry_run",
  },
};

describe("catchUpWorkflow", () => {
  it("resolveDefaultScheduleType maps presets", () => {
    expect(resolveDefaultScheduleType("past_week")).toBe("weekly");
    expect(resolveDefaultScheduleType("past_month")).toBe("monthly");
    expect(resolveDefaultScheduleType("manual")).toBe("weekly");
  });

  it("formatReportingPeriodRange renders human period", () => {
    expect(formatReportingPeriodRange("2026-06-17", "2026-06-23")).toBe("17.06.2026–23.06.2026");
  });

  it("resolveAggregatePeriodFromItems picks first item period", () => {
    expect(resolveAggregatePeriodFromItems([sampleItem])).toBe("17.06.2026–23.06.2026");
  });

  it("buildCatchUpReviewRow maps dry-run reason", () => {
    const row = buildCatchUpReviewRow(sampleItem, { isDryRunPreview: true });
    expect(row.report_code).toBe("QM_WEEKLY");
    expect(row.period_label).toBe("17.06.2026–23.06.2026");
    expect(row.due_date_label).toBe("23.06.2026");
    expect(row.reason_label).toBe("Пробный прогон (dry_run)");
    expect(row.title_final).toContain("QM weekly");
  });

  it("buildCatchUpReviewRow maps live create reason", () => {
    const liveItem: RegularTaskRunItemRow = {
      ...sampleItem,
      status: "ok",
      created_tasks: 1,
      meta: { ...sampleItem.meta, reason: undefined },
    };
    const row = buildCatchUpReviewRow(liveItem, { isDryRunPreview: false });
    expect(row.reason_label).toBe("Создание (create)");
  });

  it("buildCatchUpPayload includes schedule_type and filters", () => {
    const payload = buildCatchUpPayload(
      {
        preset: "manual",
        manualDate: "2026-06-24",
        scheduleType: "weekly",
        orgGroupId: null,
        orgUnitId: 44,
        executorRoleId: 3,
      },
      true,
    );
    expect(payload).toEqual({
      dry_run: true,
      preset: "manual",
      run_for_date: "2026-06-24",
      schedule_type: "weekly",
      org_unit_id: 44,
      executor_role_id: 3,
    });
  });

  it("validateCatchUpForm requires manual date", () => {
    expect(
      validateCatchUpForm({
        preset: "manual",
        manualDate: "",
        scheduleType: "weekly",
        orgGroupId: null,
        orgUnitId: null,
        executorRoleId: null,
      }),
    ).toMatch(/дату/);
  });

  it("payloadsEquivalent ignores dry_run flag", () => {
    const base: CatchUpRegularTasksParams = {
      dry_run: true,
      preset: "manual",
      run_for_date: "2026-06-24",
      schedule_type: "weekly",
      org_unit_id: 44,
    };
    expect(payloadsEquivalent(base, { ...base, dry_run: false })).toBe(true);
    expect(
      payloadsEquivalent(base, { ...base, org_unit_id: 45 }),
    ).toBe(false);
  });

  it("pastWeekPresetHint mentions Wednesday window", () => {
    expect(pastWeekPresetHint()).toMatch(/среда/i);
    expect(pastWeekPresetHint()).toMatch(/today−7/);
  });
});
