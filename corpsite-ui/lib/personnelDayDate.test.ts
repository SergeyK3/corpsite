import { describe, expect, it } from "vitest";

import {
  formatPersonnelDayDateForDisplay,
  isIncompletePersonnelBirthDate,
  isIncompletePersonnelDocumentDate,
  isLegacyYearOnlyDocumentDate,
  isValidPersonnelDayDateIso,
  normalizePersonnelDocumentDateInput,
  parsePersonnelDayDateInput,
  validatePersonnelDocumentDate,
} from "./personnelDayDate";

describe("personnelDayDate", () => {
  it("accepts canonical full ISO dates", () => {
    expect(isValidPersonnelDayDateIso("2018-09-15")).toBe(true);
    expect(isValidPersonnelDayDateIso("2025-01-01")).toBe(true);
  });

  it("marks legacy year-only document values as incomplete", () => {
    expect(isIncompletePersonnelDocumentDate("2018")).toBe(true);
    expect(isIncompletePersonnelDocumentDate("2018-01-01")).toBe(true);
    expect(isLegacyYearOnlyDocumentDate("01.01.2018")).toBe(true);
    expect(isIncompletePersonnelDocumentDate("15.03.2018")).toBe(false);
  });

  it("formats incomplete legacy values without inventing 01.01", () => {
    expect(formatPersonnelDayDateForDisplay("2018")).toBe("2018 (уточните дату)");
    expect(formatPersonnelDayDateForDisplay("2018-09-15")).toBe("15.09.2018");
  });

  it("parses and stores DD.MM.YYYY as ISO without day shift", () => {
    expect(parsePersonnelDayDateInput("15.09.2022")).toBe("2022-09-15");
    expect(normalizePersonnelDocumentDateInput("15.09.2022")).toBe("2022-09-15");
    expect(normalizePersonnelDocumentDateInput("2018")).toBe("2018");
  });

  it("uses day precision when checking incomplete parsed document and birth dates", () => {
    expect(parsePersonnelDayDateInput("15.09.2018")).toBe("2018-09-15");
    expect(isIncompletePersonnelDocumentDate("15.09.2018")).toBe(false);
    expect(isIncompletePersonnelDocumentDate("15.09")).toBe(true);
    expect(isIncompletePersonnelBirthDate("1990-01-01")).toBe(false);
    expect(isIncompletePersonnelBirthDate("1990")).toBe(true);
  });

  it("validates document dates for save", () => {
    expect(validatePersonnelDocumentDate("")).toBeNull();
    expect(validatePersonnelDocumentDate("2018")).toBe("Укажите полную дату в формате ДД.ММ.ГГГГ");
    expect(validatePersonnelDocumentDate("15.09.2018")).toBeNull();
  });
});
