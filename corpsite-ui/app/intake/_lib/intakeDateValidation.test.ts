import { describe, expect, it } from "vitest";

import { emptyIntakeDraftPayload } from "./intakeApi.client";
import {
  collectIntakeDateValidationIssues,
  formatIntakeDateForDisplay,
  hasBlockingIntakeDateIssues,
  isIncompleteIntakeBirthDate,
  isIncompleteIntakePeriodDate,
  isValidIntakeFullDateIso,
} from "./intakeDateValidation";

describe("intakeDateValidation", () => {
  it("accepts canonical full ISO dates", () => {
    expect(isValidIntakeFullDateIso("1990-05-20")).toBe(true);
    expect(isValidIntakeFullDateIso("2020-01-01")).toBe(true);
    expect(isValidIntakeFullDateIso("2020-02-29")).toBe(true);
  });

  it("rejects invalid calendar dates", () => {
    expect(isValidIntakeFullDateIso("2020-02-30")).toBe(false);
    expect(isValidIntakeFullDateIso("20.05.1990")).toBe(false);
  });

  it("treats year-only and partial values as incomplete on period fields", () => {
    expect(isIncompleteIntakePeriodDate("2018")).toBe(true);
    expect(isIncompleteIntakePeriodDate("20")).toBe(true);
    expect(isIncompleteIntakePeriodDate("2018-01-01")).toBe(true);
    expect(isIncompleteIntakePeriodDate("2018-09-15")).toBe(false);
    expect(isIncompleteIntakePeriodDate("")).toBe(false);
  });

  it("allows January 1 as a complete birth date", () => {
    expect(isIncompleteIntakeBirthDate("1990-01-01")).toBe(false);
    expect(isIncompleteIntakeBirthDate("1990")).toBe(true);
    expect(isIncompleteIntakeBirthDate("01.01.1990")).toBe(false);
  });

  it("formats incomplete legacy values without inventing 01.01", () => {
    expect(formatIntakeDateForDisplay("2018", "period")).toBe("2018 (уточните дату)");
    expect(formatIntakeDateForDisplay("2018-01-01", "period")).toBe("2018 (уточните дату)");
    expect(formatIntakeDateForDisplay("2018-09-15", "period")).toBe("15.09.2018");
    expect(formatIntakeDateForDisplay("1990-05-20", "birth")).toBe("20.05.1990");
  });

  it("blocks submit when any filled date field is incomplete", () => {
    const payload = emptyIntakeDraftPayload();
    payload.personal.birth_date = "1990-05-20";
    payload.education = [
      {
        education_type: "basic",
        institution: "КазНУ",
        year_from: "2014",
        year_to: "2018-06-30",
        specialty: "",
        qualification: "",
        diploma_number: "",
      },
    ];

    const issues = collectIntakeDateValidationIssues(payload);
    expect(issues.map((issue) => issue.field)).toEqual(["education[0].year_from"]);
    expect(issues[0]?.message).toBe("Образование → КазНУ → дата поступления");
    expect(issues[0]?.focusTestId).toBe("intake-education-year-from-0");
    expect(hasBlockingIntakeDateIssues(payload)).toBe(true);
  });

  it("builds contextual labels for training and relatives", () => {
    const payload = emptyIntakeDraftPayload();
    payload.training = [
      {
        institution: "Центр",
        year: "2020",
        course_name: "Актуальные вопросы ОЗ",
        hours: "",
      },
    ];
    payload.relatives = [
      {
        relationship: "мать",
        full_name: "Макалкина Татьяна Владимировна",
        birth_year: "1970",
        work_place: "",
      },
    ];

    const issues = collectIntakeDateValidationIssues(payload);
    expect(issues.map((issue) => issue.message)).toEqual([
      "Обучение → Актуальные вопросы ОЗ → дата окончания",
      "Родственники → Макалкина Татьяна Владимировна → дата рождения",
    ]);
  });

  it("does not duplicate identical field issues", () => {
    const payload = emptyIntakeDraftPayload();
    payload.education = [
      {
        education_type: "basic",
        institution: "КазНУ",
        year_from: "2014",
        year_to: "2018",
        specialty: "",
        qualification: "",
        diploma_number: "",
      },
    ];

    const issues = collectIntakeDateValidationIssues(payload);
    const fields = issues.map((issue) => issue.field);
    expect(new Set(fields).size).toBe(fields.length);
  });

  it("allows submit when all filled dates are full day precision", () => {
    const payload = emptyIntakeDraftPayload();
    payload.personal.birth_date = "1990-05-20";
    payload.education = [
      {
        education_type: "basic",
        institution: "КазНУ",
        year_from: "2014-09-01",
        year_to: "2018-06-30",
        specialty: "",
        qualification: "",
        diploma_number: "",
      },
    ];
    payload.training = [
      {
        institution: "Центр",
        year_from: "2021-03-10",
        year_to: "2021-03-10",
        course_name: "Охрана труда",
        hours: "8",
        hours_is_manual: false,
      },
    ];
    payload.relatives = [{ relationship: "мать", full_name: "Иванова", birth_year: "1965-04-12", work_place: "" }];
    payload.employment_biography = [
      {
        organization: "ООО Альфа",
        position: "Инженер",
        year_from: "2020-01-15",
        year_to: "2024-08-01",
        reason_for_leaving: "",
      },
    ];

    expect(collectIntakeDateValidationIssues(payload)).toEqual([]);
    expect(hasBlockingIntakeDateIssues(payload)).toBe(false);
  });
});
