import { describe, expect, it } from "vitest";

import {
  applyTrainingEntryPatch,
  countInclusiveCalendarDays,
  isInvalidIntakeTrainingPeriodRange,
  normalizeIntakeTrainingEntry,
  reconcileTrainingEntryHours,
  resolveIntakeTrainingPeriodRangeError,
  resolveTrainingHoursState,
} from "./intakeTraining";
import { INTAKE_PERIOD_RANGE_ERROR } from "./intakePeriodRange";

/** Raw training row shape as stored in intake draft JSON (WP-001 §4.4). */
const APPLICATION_178_TRAINING_ROW = {
  institution: "Учебный центр охраны труда",
  course_name: "Охрана труда и техника безопасности",
  year_from: "2024-07-10",
  year_to: "2024-06-01",
  document_type: "certificate",
  document_number: "ОТ-178-01",
  hours: "40",
  hours_is_manual: true,
} as const;

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

  it("flags reversed period for application 178 draft row even with manual hours", () => {
    expect(isInvalidIntakeTrainingPeriodRange(APPLICATION_178_TRAINING_ROW)).toBe(true);
    expect(resolveIntakeTrainingPeriodRangeError(APPLICATION_178_TRAINING_ROW)).toBe(
      INTAKE_PERIOD_RANGE_ERROR,
    );

    const item = normalizeIntakeTrainingEntry(APPLICATION_178_TRAINING_ROW);
    expect(resolveTrainingHoursState(item)).toMatchObject({
      hours: "40",
      note: "По документу",
      isManual: true,
      periodError: INTAKE_PERIOD_RANGE_ERROR,
    });
  });

  it("accepts valid application 178 period when only dates are corrected", () => {
    const validRow = {
      ...APPLICATION_178_TRAINING_ROW,
      year_from: "2024-05-10",
      year_to: "2024-06-01",
    };

    expect(isInvalidIntakeTrainingPeriodRange(validRow)).toBe(false);
    expect(resolveIntakeTrainingPeriodRangeError(validRow)).toBeNull();
    expect(resolveTrainingHoursState(normalizeIntakeTrainingEntry(validRow)).periodError).toBeNull();
  });

  it("reads legacy year as period end from raw draft payload", () => {
    const legacyRow = {
      institution: "Учебный центр охраны труда",
      course_name: "Охрана труда и техника безопасности",
      year_from: "2024-07-10",
      year: "2024-06-01",
      hours: "40",
      hours_is_manual: true,
    };

    expect(isInvalidIntakeTrainingPeriodRange(legacyRow)).toBe(true);
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
    expect(resolveTrainingHoursState(invalid).periodError).toBe(
      "Дата окончания не может быть раньше даты начала",
    );
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
