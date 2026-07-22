import { describe, expect, it } from "vitest";

import {
  formatIntakeEducationReviewLine,
  formatIntakePeriodForDisplay,
  formatIntakePeriodRange,
  formatIntakeTrainingReviewLine,
  parseIntakePeriodInput,
} from "./intakePeriodFormat";

describe("intakePeriodFormat", () => {
  it("displays saved four-digit year as-is", () => {
    expect(formatIntakePeriodForDisplay("2018", "year")).toBe("2018");
    expect(formatIntakePeriodForDisplay("2022", "year")).toBe("2022");
  });

  it("displays saved ISO date according to field precision", () => {
    expect(formatIntakePeriodForDisplay("2018-09-15", "year")).toBe("2018");
    expect(formatIntakePeriodForDisplay("1990-05-20", "day")).toBe("20.05.1990");
  });

  it("returns empty string for empty values without Invalid Date", () => {
    expect(formatIntakePeriodForDisplay("", "year")).toBe("");
    expect(formatIntakePeriodForDisplay("   ", "year")).toBe("");
    expect(formatIntakePeriodRange("", "")).toBe("—");
  });

  it("keeps partial year input without coercing to a fake full date", () => {
    expect(parseIntakePeriodInput("20", "year")).toBe("20");
    expect(parseIntakePeriodInput("202", "year")).toBe("202");
  });

  it("stores year-only values without inventing a day", () => {
    expect(parseIntakePeriodInput("2022", "year")).toBe("2022");
    expect(parseIntakePeriodInput("15.09.2022", "year")).toBe("2022");
  });

  it("preserves full ISO date when user enters DD.MM.YYYY on day-precision fields", () => {
    expect(parseIntakePeriodInput("15.09.2018", "day")).toBe("2018-09-15");
  });

  it("formats education and training review lines", () => {
    expect(
      formatIntakeEducationReviewLine({
        institution: "КазНУ",
        year_from: "2014",
        year_to: "2018",
      }),
    ).toBe("КазНУ: 2014 — 2018");

    expect(
      formatIntakeTrainingReviewLine({
        course_name: "Охрана труда",
        year: "2021",
      }),
    ).toBe("Охрана труда (2021)");
  });

  it("restores previously saved ISO education period for display", () => {
    expect(formatIntakePeriodRange("2014-09-01", "2018-06-30", "year")).toBe("2014 — 2018");
  });
});
