import { describe, expect, it } from "vitest";
import { emptyIntakeDraftPayload, toCanonicalIntakeV2, toIntakeFormPayload } from "./intakeApi.client";
import { emptyIntakeEducationEntry } from "./intakeEducation";
import { emptyIntakeAcademicDegreeEntry, emptyIntakeForeignLanguageEntry } from "./intakeAdditional";
import { isIntakeListRowEmpty } from "./intakeEmptyRows";
import { collectIntakeSubmitIssues } from "./intakeSubmitValidation";
import { formatTypedIntakePeriodDate, parseIntakePeriodInput } from "./intakePeriodFormat";

describe("intake row and date handling", () => {
  it("omits blank legacy rows at save and PDF read, retaining partial entries", () => {
    const payload = emptyIntakeDraftPayload();
    payload.education = [emptyIntakeEducationEntry(), { ...emptyIntakeEducationEntry(), institution: "Колледж" }];
    payload.additional.foreign_languages = [emptyIntakeForeignLanguageEntry(), { language: "английский", proficiency: "" }];
    const saved = toCanonicalIntakeV2(payload);
    expect((saved.education as unknown[]).length).toBe(1);
    expect(((saved.additional as { foreign_languages: unknown[] }).foreign_languages).length).toBe(1);
    const forPdf = toIntakeFormPayload(payload);
    expect(forPdf.education).toHaveLength(1);
    expect(forPdf.additional.foreign_languages).toHaveLength(1);
    expect(isIntakeListRowEmpty("education", emptyIntakeEducationEntry())).toBe(true);
  });

  it("flags missing fields only in partial rows and invalid phone", () => {
    const payload = emptyIntakeDraftPayload();
    payload.contacts.mobile_phone = "+7701234567";
    payload.additional.foreign_languages = [emptyIntakeForeignLanguageEntry(), { language: "английский", proficiency: "" }];
    expect(collectIntakeSubmitIssues(payload).map((issue) => issue.focusTestId)).toEqual([
      "intake-mobile-phone", "intake-foreign-language-proficiency-1",
    ]);
  });

  it("formats a typed full date and preserves a year entry", () => {
    expect(formatTypedIntakePeriodDate("25092024")).toBe("25.09.2024");
    expect(parseIntakePeriodInput("25092024")).toBe("2024-09-25");
    expect(formatTypedIntakePeriodDate("2024")).toBe("2024");
    expect(parseIntakePeriodInput("2024")).toBe("2024");
  });

  it("requires the missing degree after retaining a date-only academic row", () => {
    const payload = emptyIntakeDraftPayload();
    payload.contacts.mobile_phone = "+77012345678";
    payload.additional.academic_degrees = [{ ...emptyIntakeAcademicDegreeEntry(), completed_at: "2024-09-25" }];
    expect(collectIntakeSubmitIssues(payload).map((issue) => issue.focusTestId)).toEqual([
      "intake-academic-degree-degree-0",
    ]);
  });
});
