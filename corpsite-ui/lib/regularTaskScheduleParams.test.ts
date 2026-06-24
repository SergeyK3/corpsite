import { describe, expect, it } from "vitest";

import {
  DEFAULT_SCHEDULE_PARAMS,
  defaultScheduleParamsJson,
  resolveScheduleParamsOnTypeChange,
  validateScheduleParams,
} from "./regularTaskScheduleParams";

describe("resolveScheduleParamsOnTypeChange", () => {
  it("inserts bymonthday when switching to monthly from weekly default", () => {
    const weeklyDefault = JSON.stringify(DEFAULT_SCHEDULE_PARAMS.weekly, null, 2);
    const result = resolveScheduleParamsOnTypeChange("weekly", "monthly", weeklyDefault);

    expect(JSON.parse(result)).toEqual(DEFAULT_SCHEDULE_PARAMS.monthly);
  });

  it("inserts bymonth and bymonthday when switching to yearly from monthly default", () => {
    const monthlyDefault = JSON.stringify(DEFAULT_SCHEDULE_PARAMS.monthly, null, 2);
    const result = resolveScheduleParamsOnTypeChange("monthly", "yearly", monthlyDefault);

    expect(JSON.parse(result)).toEqual(DEFAULT_SCHEDULE_PARAMS.yearly);
  });

  it("replaces empty JSON when selecting a schedule type", () => {
    const result = resolveScheduleParamsOnTypeChange("", "monthly", "{}");

    expect(JSON.parse(result)).toEqual(DEFAULT_SCHEDULE_PARAMS.monthly);
  });

  it("keeps custom JSON that no longer matches the previous default", () => {
    const customWeekly = JSON.stringify({ byweekday: [3], time: "09:30" }, null, 2);
    const result = resolveScheduleParamsOnTypeChange("weekly", "monthly", customWeekly);

    expect(result).toBe(customWeekly);
  });
});

describe("validateScheduleParams", () => {
  it("accepts weekly params with byweekday", () => {
    expect(
      validateScheduleParams("weekly", { byweekday: [1], time: "10:00" }),
    ).toBeNull();
  });

  it("rejects monthly params without bymonthday", () => {
    expect(validateScheduleParams("monthly", { time: "10:00" })).toBe(
      "Для ежемесячного расписания обязателен параметр bymonthday.",
    );
  });

  it("rejects invalid time format", () => {
    expect(validateScheduleParams("weekly", { byweekday: [1], time: "25:00" })).toBe(
      "Параметр time должен быть в формате HH:MM (например, 10:00).",
    );
  });

  it("provides default JSON templates", () => {
    expect(JSON.parse(defaultScheduleParamsJson("weekly"))).toEqual(DEFAULT_SCHEDULE_PARAMS.weekly);
    expect(JSON.parse(defaultScheduleParamsJson("monthly"))).toEqual(DEFAULT_SCHEDULE_PARAMS.monthly);
    expect(JSON.parse(defaultScheduleParamsJson("yearly"))).toEqual(DEFAULT_SCHEDULE_PARAMS.yearly);
  });
});
