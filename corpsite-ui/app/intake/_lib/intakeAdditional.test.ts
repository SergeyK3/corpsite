import { describe, expect, it } from "vitest";

import {
  emptyIntakeAcademicDegreeEntry,
  emptyIntakeAcademicTitleEntry,
  formatIntakeAcademicDegreeReviewLine,
  formatIntakeAcademicTitleReviewLine,
  formatIntakeAwardReviewLine,
  formatIntakeForeignLanguageReviewLine,
  normalizeIntakeAcademicDegreeEntry,
  normalizeIntakeAcademicTitleEntry,
  normalizeIntakeAdditionalPayload,
  normalizeIntakeAwardEntry,
  normalizeIntakeForeignLanguageEntry,
  resolveIntakeAcademicDegreeDisplay,
  resolveIntakeAcademicTitleDisplay,
  resolveIntakeAwardCategoryDisplay,
  resolveIntakeAwardNameDisplay,
} from "./intakeAdditional";
import { emptyIntakeDraftPayload } from "./intakeApi.client";

describe("intakeAdditional", () => {
  it("normalizes legacy payloads without additional block", () => {
    const legacy = { foreign_languages: [{ language: "English", proficiency: "B2" }] };
    expect(normalizeIntakeAdditionalPayload(legacy as never)).toEqual({
      foreign_languages: [{ language: "English", proficiency: "B2" }],
      foreign_languages_none: false,
      awards: [],
      awards_none: false,
      academic_degrees: [],
      academic_degrees_none: false,
      academic_titles: [],
      academic_titles_none: false,
    });
  });

  it("maps legacy award title to category or exact name", () => {
    expect(normalizeIntakeAwardEntry({ title: "Ведомственная награда" })).toEqual({
      category: "Ведомственная",
      name: "",
      issued_by: "",
      awarded_at: "",
      document_number: "",
    });
    expect(normalizeIntakeAwardEntry({ title: "Орден «Парасат»", date: "2020-05-10" })).toEqual({
      category: "",
      name: "Орден «Парасат»",
      issued_by: "",
      awarded_at: "2020-05-10",
      document_number: "",
    });
  });

  it("migrates legacy academic degree label and degree_type", () => {
    const migrated = normalizeIntakeAcademicDegreeEntry({
      label: "Кандидат медицинских наук",
      degree_type: "Медицина",
      completed_at: "2018-06-30",
    });
    expect(migrated.degree).toBe("Другое");
    expect(migrated.degree_other).toBe("Кандидат медицинских наук");
    expect(migrated.field_of_science).toBe("Медицина");
    expect(migrated.completed_at).toBe("2018-06-30");
  });

  it("splits legacy combined academic row into degree and title lists", () => {
    const normalized = normalizeIntakeAdditionalPayload({
      academic_degrees: [
        {
          degree: "PhD",
          field_of_science: "Экономика",
          academic_title: "Доцент",
          completed_at: "2019-05-01",
          document_number: "LEG-1",
        },
      ],
    });
    expect(normalized.academic_degrees).toHaveLength(1);
    expect(normalized.academic_degrees[0].document_number).toBe("LEG-1");
    expect(normalized.academic_titles).toHaveLength(1);
    expect(normalized.academic_titles[0].academic_title).toBe("Доцент");
    expect(normalized.academic_titles[0].document_number).toBe("LEG-1");
  });

  it("keeps structured academic degree and title fields separate", () => {
    expect(
      normalizeIntakeAcademicDegreeEntry({
        degree: "Доктор наук",
        field_of_science: "Экономика",
        completed_at: "2020-01-01",
        document_number: "DN-1",
      }),
    ).toEqual({
      degree: "Доктор наук",
      degree_other: "",
      field_of_science: "Экономика",
      completed_at: "2020-01-01",
      document_number: "DN-1",
    });
    expect(
      normalizeIntakeAcademicTitleEntry({
        academic_title: "Профессор",
        field_of_science: "Экономика",
        completed_at: "2021-02-02",
        document_number: "TTL-1",
      }),
    ).toEqual({
      academic_title: "Профессор",
      academic_title_other: "",
      field_of_science: "Экономика",
      completed_at: "2021-02-02",
      document_number: "TTL-1",
    });
  });

  it("formats review lines", () => {
    expect(
      formatIntakeForeignLanguageReviewLine(
        normalizeIntakeForeignLanguageEntry({ language: "Английский", proficiency: "Выше среднего (B2)" }),
      ),
    ).toBe("Английский (Выше среднего (B2))");
    expect(
      formatIntakeAwardReviewLine(
        normalizeIntakeAwardEntry({
          category: "Медаль",
          name: "Медаль «За доблестный труд»",
          awarded_at: "2020-05-10",
        }),
      ),
    ).toContain("Медаль «За доблестный труд»");
    expect(
      formatIntakeAcademicDegreeReviewLine(
        normalizeIntakeAcademicDegreeEntry({
          ...emptyIntakeAcademicDegreeEntry(),
          degree: "PhD",
          completed_at: "2019-12-01",
        }),
      ),
    ).toContain("PhD");
    expect(
      formatIntakeAcademicTitleReviewLine(
        normalizeIntakeAcademicTitleEntry({
          ...emptyIntakeAcademicTitleEntry(),
          academic_title: "Доцент",
          completed_at: "2020-03-01",
        }),
      ),
    ).toContain("Доцент");
  });

  it("resolves academic degree and title display separately", () => {
    const degree = normalizeIntakeAcademicDegreeEntry({
      degree: "Другое",
      degree_other: "Магистр права",
    });
    const title = normalizeIntakeAcademicTitleEntry({
      academic_title: "Другое",
      academic_title_other: "Старший преподаватель",
    });
    expect(resolveIntakeAcademicDegreeDisplay(degree)).toBe("Магистр права");
    expect(resolveIntakeAcademicTitleDisplay(title)).toBe("Старший преподаватель");
  });

  it("resolves award name and category display separately", () => {
    const award = normalizeIntakeAwardEntry({
      category: "Благодарность",
      name: "Благодарность Министерства здравоохранения",
    });
    expect(resolveIntakeAwardNameDisplay(award)).toBe("Благодарность Министерства здравоохранения");
    expect(resolveIntakeAwardCategoryDisplay(award)).toBe("Благодарность");
  });

  it("includes additional defaults in empty draft payload", () => {
    expect(emptyIntakeDraftPayload().additional).toEqual(normalizeIntakeAdditionalPayload(undefined));
  });
});
