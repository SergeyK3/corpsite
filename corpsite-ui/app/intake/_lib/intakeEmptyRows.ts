import type { IntakeDraftPayload } from "./intakeApi.client";

export type IntakeListSection =
  | "education" | "training" | "relatives" | "employment_biography"
  | "foreign_languages" | "awards" | "academic_degrees" | "academic_titles";

const CONTENT_FIELDS: Record<IntakeListSection, readonly string[]> = {
  education: ["start_date", "end_date", "year_from", "year_to", "institution_original", "institution_normalized", "institution", "specialty_original", "specialty", "qualification_original", "qualification", "document_number", "diploma_number", "document_date", "city", "evidence_document_ids"],
  training: ["start_date", "end_date", "year_from", "year_to", "year", "course_name_original", "course_name", "institution_original", "institution", "specialty_original", "specialty", "document_number", "document_date", "hours", "evidence_document_ids"],
  relatives: ["relationship_other", "full_name", "birth_date", "birth_year", "workplace", "work_place"],
  employment_biography: ["start_date", "end_date", "year_from", "year_to", "organization_original", "organization_normalized", "organization", "city", "position_original", "position_normalized", "position", "reason_for_leaving", "note", "evidence_document_ids"],
  foreign_languages: ["language", "proficiency"],
  awards: ["category", "name", "title", "issued_by", "awarded_at", "date", "document_number"],
  academic_degrees: ["degree", "degree_other", "field_of_science", "completed_at", "document_number", "label", "degree_type"],
  academic_titles: ["academic_title", "academic_title_other", "field_of_science", "completed_at", "document_number", "label", "degree_type"],
};

function hasValue(value: unknown): boolean {
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === "number") return Number.isFinite(value);
  return typeof value === "string" && value.trim().length > 0;
}

export function isIntakeListRowEmpty(section: IntakeListSection, item: unknown): boolean {
  if (!item || typeof item !== "object") return true;
  const row = item as Record<string, unknown>;
  if (section === "relatives" && hasValue(row.relationship) && String(row.relationship).toLowerCase() !== "другое") return false;
  return !CONTENT_FIELDS[section].some((field) => hasValue(row[field]));
}

export function stripEmptyIntakeRows(payload: IntakeDraftPayload): IntakeDraftPayload {
  return {
    ...payload,
    education: payload.education.filter((item) => !isIntakeListRowEmpty("education", item)),
    training: payload.training.filter((item) => !isIntakeListRowEmpty("training", item)),
    relatives: payload.relatives.filter((item) => !isIntakeListRowEmpty("relatives", item)),
    employment_biography: payload.employment_biography.filter((item) => !isIntakeListRowEmpty("employment_biography", item)),
    additional: {
      ...payload.additional,
      foreign_languages: payload.additional.foreign_languages.filter((item) => !isIntakeListRowEmpty("foreign_languages", item)),
      awards: payload.additional.awards.filter((item) => !isIntakeListRowEmpty("awards", item)),
      academic_degrees: payload.additional.academic_degrees.filter((item) => !isIntakeListRowEmpty("academic_degrees", item)),
      academic_titles: payload.additional.academic_titles.filter((item) => !isIntakeListRowEmpty("academic_titles", item)),
    },
  };
}
