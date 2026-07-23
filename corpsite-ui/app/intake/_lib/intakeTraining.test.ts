import { describe, expect, it } from "vitest";

import {
  applyTrainingEntryPatch,
  countInclusiveCalendarDays,
  normalizeIntakeTrainingEntry,
  reconcileTrainingEntryHours,
  resolveTrainingHoursState,
} from "./intakeTraining";

describe("intakeTraining hours calculation", () => {
  it("calculates inclusive calendar days multiplied by eight", () => {
    expect(countInclusiveCalendarDays("2021-03-10", "2021-03-10")).toBe(1);
    expect(countInclusiveCalendarDays("2021-03-10", "2021-03-12")).toBe(3);
  });

  it("returns calculated hours and note when hours are not manual", () => {
    const item = normalizeIntakeTrainingEntry({
      course_name: "Охрана труда",
      year_from: "2021-03-10",
      year_to: "2021-03-12",
      hours: "",
      hours_is_manual: false,
    });

    expect(resolveTrainingHoursState(item)).toEqual({
      hours: "24",
      note: "Расчётно: 3 дней × 8 часов",
      isManual: false,
      periodError: null,
    });
    expect(reconcileTrainingEntryHours(item).hours).toBe("24");
  });

  it("keeps manual hours and shows document note", () => {
    const item = normalizeIntakeTrainingEntry({
      year_from: "2021-03-10",
      year_to: "2021-03-12",
      hours: "72",
      hours_is_manual: true,
    });

    expect(resolveTrainingHoursState(item)).toEqual({
      hours: "72",
      note: "По документу",
      isManual: true,
      periodError: null,
    });
  });

  it("recalculates only when hours are not manual and dates change", () => {
    const base = normalizeIntakeTrainingEntry({
      year_from: "2021-03-10",
      year_to: "2021-03-10",
      hours: "",
      hours_is_manual: false,
    });

    const recalculated = applyTrainingEntryPatch(base, { year_to: "2021-03-12" });
    expect(recalculated.hours).toBe("24");
    expect(recalculated.hours_is_manual).toBe(false);

    const manual = normalizeIntakeTrainingEntry({
      ...base,
      hours: "40",
      hours_is_manual: true,
    });
    const unchanged = applyTrainingEntryPatch(manual, { year_to: "2021-03-12" });
    expect(unchanged.hours).toBe("40");
    expect(unchanged.hours_is_manual).toBe(true);
  });

  it("does not calculate hours for incomplete or invalid periods", () => {
    const incomplete = normalizeIntakeTrainingEntry({
      year_from: "2021",
      year_to: "2021-03-12",
      hours: "",
      hours_is_manual: false,
    });
    expect(resolveTrainingHoursState(incomplete).periodError).toContain("полные даты");

    const invalid = normalizeIntakeTrainingEntry({
      year_from: "2021-03-12",
      year_to: "2021-03-10",
      hours: "",
      hours_is_manual: false,
    });
    expect(resolveTrainingHoursState(invalid).periodError).toContain("не может быть позже");
  });

  it("migrates legacy year field into year_to on normalize", () => {
    expect(
      normalizeIntakeTrainingEntry({
        institution: "Центр",
        course_name: "Охрана труда",
        year: "2021-03-10",
        hours: "72",
      }),
    ).toMatchObject({
      year_to: "2021-03-10",
      hours: "72",
    });
  });
});
