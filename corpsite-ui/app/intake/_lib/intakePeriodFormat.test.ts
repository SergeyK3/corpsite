import { describe, expect, it } from "vitest";

import {
  formatIntakeBirthDateForDisplay,
  formatIntakeEducationReviewLine,
  formatIntakeEmploymentReviewLine,
  formatIntakePeriodForDisplay,
  formatIntakePeriodRange,
  formatIntakeRelativeReviewLine,
  formatIntakeTrainingReviewLine,
  parseIntakePeriodInput,
} from "./intakePeriodFormat";

describe("intakePeriodFormat", () => {
  it("displays saved full ISO dates as DD.MM.YYYY", () => {
    expect(formatIntakePeriodForDisplay("2018-09-15")).toBe("15.09.2018");
    expect(formatIntakeBirthDateForDisplay("1990-05-20")).toBe("20.05.1990");
  });

  it("marks legacy year-only values as needing clarification", () => {
    expect(formatIntakePeriodForDisplay("2018")).toBe("2018 (уточните дату)");
    expect(formatIntakePeriodForDisplay("2018-01-01")).toBe("2018 (уточните дату)");
  });

  it("returns empty string for empty values without Invalid Date", () => {
    expect(formatIntakePeriodForDisplay("")).toBe("");
    expect(formatIntakePeriodRange("", "")).toBe("—");
  });

  it("stores user-entered DD.MM.YYYY as canonical ISO", () => {
    expect(parseIntakePeriodInput("15.09.2018")).toBe("2018-09-15");
  });

  it("formats education, training, relatives and employment review lines", () => {
    expect(
      formatIntakeEducationReviewLine({
        institution: "КазНУ",
        year_from: "2014-09-01",
        year_to: "2018-06-30",
      }),
    ).toBe("КазНУ: 01.09.2014 — 30.06.2018");

    expect(
      formatIntakeTrainingReviewLine({
        course_name: "Охрана труда",
        year: "2021-03-10",
      }),
    ).toBe("Охрана труда (10.03.2021)");

    expect(
      formatIntakeRelativeReviewLine({
        full_name: "Иванова М.И.",
        birth_year: "1965-04-12",
      }),
    ).toBe("Иванова М.И., 12.04.1965");

    expect(
      formatIntakeEmploymentReviewLine({
        organization: "ООО Альфа",
        position: "Инженер",
        year_from: "2020-01-15",
        year_to: "2024-08-01",
      }),
    ).toBe("ООО Альфа — Инженер: 15.01.2020 — 01.08.2024");
  });

  it("shows incomplete legacy periods on review step", () => {
    expect(
      formatIntakeEducationReviewLine({
        institution: "КазНУ",
        year_from: "2014",
        year_to: "2018",
      }),
    ).toBe("КазНУ: 2014 (уточните дату) — 2018 (уточните дату)");
  });
});
