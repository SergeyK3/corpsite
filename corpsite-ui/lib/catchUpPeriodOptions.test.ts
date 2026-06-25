// FILE: corpsite-ui/lib/catchUpPeriodOptions.test.ts

import { describe, expect, it } from "vitest";

import { buildCatchUpPayload } from "./catchUpWorkflow";
import {
  buildCatchUpPeriodOptions,
  formatMonthYearLabel,
  formatWeekRangeLabel,
  prevWeekPeriodBounds,
  resolvePastWeekRunForDate,
} from "./catchUpPeriodOptions";

const FIXED_TODAY = new Date(2026, 5, 25); // 25 Jun 2026

describe("catchUpPeriodOptions", () => {
  it("weekly options use DD.MM–DD.MM.YYYY labels", () => {
    const options = buildCatchUpPeriodOptions("weekly", FIXED_TODAY, 3);
    expect(options.length).toBeGreaterThanOrEqual(2);
    expect(options[0]?.label).toMatch(/^\d{2}\.\d{2}–\d{2}\.\d{2}\.\d{4}$/);
    expect(options[0]?.preset).toBe("past_week");
    expect(options[0]?.manualDate).toBe("");
    expect(options[1]?.preset).toBe("manual");
    expect(options[1]?.manualDate).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it("monthly options use calendar month labels", () => {
    const options = buildCatchUpPeriodOptions("monthly", FIXED_TODAY, 3);
    expect(options[0]?.preset).toBe("past_month");
    expect(options[0]?.label).toBe("Апрель 2026");
    expect(formatMonthYearLabel(new Date(2026, 3, 1))).toBe("Апрель 2026");
  });

  it("yearly options display reporting year", () => {
    const options = buildCatchUpPeriodOptions("yearly", FIXED_TODAY, 3);
    expect(options[0]?.label).toBe("2025");
    expect(options[0]?.preset).toBe("manual");
    expect(options[0]?.manualDate).toBe("2026-01-01");
    expect(options[1]?.label).toBe("2024");
  });

  it("changing schedule type changes available period options", () => {
    const weekly = buildCatchUpPeriodOptions("weekly", FIXED_TODAY, 2);
    const monthly = buildCatchUpPeriodOptions("monthly", FIXED_TODAY, 2);
    expect(weekly[0]?.key.startsWith("weekly:")).toBe(true);
    expect(monthly[0]?.key.startsWith("monthly:")).toBe(true);
    expect(weekly[0]?.key).not.toBe(monthly[0]?.key);
  });

  it("formatWeekRangeLabel omits repeated year inside same year", () => {
    const start = new Date(2026, 5, 17);
    const end = new Date(2026, 5, 23);
    expect(formatWeekRangeLabel(start, end)).toBe("17.06–23.06.2026");
  });

  it("resolvePastWeekRunForDate matches backend wednesday window", () => {
    const runFor = resolvePastWeekRunForDate(FIXED_TODAY);
    expect(runFor.getDay()).toBe(3);
    const { start, end } = prevWeekPeriodBounds(runFor);
    expect(formatWeekRangeLabel(start, end)).toBe("17.06–23.06.2026");
  });

  it("maps selected period to compatible catch-up payload", () => {
    const monthly = buildCatchUpPeriodOptions("monthly", FIXED_TODAY, 1)[0]!;
    const payload = buildCatchUpPayload(
      {
        preset: monthly.preset,
        manualDate: monthly.manualDate,
        scheduleType: "monthly",
        orgGroupId: null,
        orgUnitId: null,
        executorRoleId: null,
        regularTaskId: 12,
      },
      true,
    );
    expect(payload).toEqual({
      dry_run: true,
      preset: "past_month",
      schedule_type: "monthly",
      regular_task_id: 12,
    });

    const weeklyManual = buildCatchUpPeriodOptions("weekly", FIXED_TODAY, 2)[1]!;
    const manualPayload = buildCatchUpPayload(
      {
        preset: weeklyManual.preset,
        manualDate: weeklyManual.manualDate,
        scheduleType: "weekly",
        orgGroupId: null,
        orgUnitId: null,
        executorRoleId: null,
        regularTaskId: null,
      },
      true,
    );
    expect(manualPayload.preset).toBe("manual");
    expect(manualPayload.run_for_date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(manualPayload.schedule_type).toBe("weekly");
  });
});
