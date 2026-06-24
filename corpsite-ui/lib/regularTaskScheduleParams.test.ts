import { describe, expect, it } from "vitest";

import {
  DEFAULT_SCHEDULE_PARAMS,
  defaultScheduleParamsJson,
  resolveScheduleParamsOnTypeChange,
  scheduleParamKeysForType,
  validateScheduleParams,
} from "./regularTaskScheduleParams";

function parsedKeys(json: string): string[] {
  return Object.keys(JSON.parse(json)).sort();
}

describe("resolveScheduleParamsOnTypeChange", () => {
  it("weekly → monthly resets JSON to bymonthday default", () => {
    const customWeekly = JSON.stringify({ byweekday: [3], time: "09:30" }, null, 2);
    const result = resolveScheduleParamsOnTypeChange("weekly", "monthly", customWeekly);

    expect(JSON.parse(result)).toEqual(DEFAULT_SCHEDULE_PARAMS.monthly);
    expect(parsedKeys(result)).toEqual(scheduleParamKeysForType("monthly"));
    expect(JSON.parse(result)).not.toHaveProperty("byweekday");
  });

  it("monthly → weekly resets JSON to byweekday default", () => {
    const customMonthly = JSON.stringify({ bymonthday: [15], time: "08:00" }, null, 2);
    const result = resolveScheduleParamsOnTypeChange("monthly", "weekly", customMonthly);

    expect(JSON.parse(result)).toEqual(DEFAULT_SCHEDULE_PARAMS.weekly);
    expect(parsedKeys(result)).toEqual(scheduleParamKeysForType("weekly"));
    expect(JSON.parse(result)).not.toHaveProperty("bymonthday");
    expect(JSON.parse(result)).not.toHaveProperty("bymonth");
  });

  it("monthly → yearly resets JSON to bymonth + bymonthday default", () => {
    const monthlyDefault = JSON.stringify(DEFAULT_SCHEDULE_PARAMS.monthly, null, 2);
    const result = resolveScheduleParamsOnTypeChange("monthly", "yearly", monthlyDefault);

    expect(JSON.parse(result)).toEqual(DEFAULT_SCHEDULE_PARAMS.yearly);
    expect(parsedKeys(result)).toEqual(scheduleParamKeysForType("yearly"));
    expect(JSON.parse(result)).not.toHaveProperty("byweekday");
  });

  it("replaces empty JSON when selecting a schedule type", () => {
    const result = resolveScheduleParamsOnTypeChange("", "monthly", "{}");

    expect(JSON.parse(result)).toEqual(DEFAULT_SCHEDULE_PARAMS.monthly);
  });

  it("does not replace JSON when schedule_type is unchanged", () => {
    const customMonthly = JSON.stringify({ bymonthday: [15], time: "08:00" }, null, 2);
    const result = resolveScheduleParamsOnTypeChange("monthly", "monthly", customMonthly);

    expect(result).toBe(customMonthly);
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

  it("accepts time values with seconds like backend parser", () => {
    expect(validateScheduleParams("monthly", { bymonthday: [1], time: "10:00:00" })).toBeNull();
  });

  it("provides default JSON templates", () => {
    expect(JSON.parse(defaultScheduleParamsJson("weekly"))).toEqual(DEFAULT_SCHEDULE_PARAMS.weekly);
    expect(JSON.parse(defaultScheduleParamsJson("monthly"))).toEqual(DEFAULT_SCHEDULE_PARAMS.monthly);
    expect(JSON.parse(defaultScheduleParamsJson("yearly"))).toEqual(DEFAULT_SCHEDULE_PARAMS.yearly);
  });
});
