import {
  emptyIntakeDraftPayload,
  type IntakeAcademicDegree,
  type IntakeAcademicTitle,
  type IntakeAdditionalPayload,
  type IntakeAward,
  type IntakeForeignLanguage,
} from "./intakeApi.client";
import {
  INTAKE_ACADEMIC_DEGREE_OPTIONS,
  INTAKE_ACADEMIC_DEGREE_OTHER,
  INTAKE_ACADEMIC_TITLE_OPTIONS,
  INTAKE_ACADEMIC_TITLE_OTHER,
  INTAKE_AWARD_CATEGORY_OPTIONS,
  INTAKE_AWARD_OTHER,
  INTAKE_FOREIGN_LANGUAGE_OPTIONS,
  INTAKE_FOREIGN_LANGUAGE_OTHER,
} from "./intakeAdditionalDictionary";
import { formatIntakeDateForDisplay } from "./intakeDateValidation";

export type IntakeForeignLanguageRow = { item: IntakeForeignLanguage; index: number };
export type IntakeAwardRow = { item: IntakeAward; index: number };
export type IntakeAcademicDegreeRow = { item: IntakeAcademicDegree; index: number };
export type IntakeAcademicTitleRow = { item: IntakeAcademicTitle; index: number };

const KNOWN_LANGUAGE_VALUES = new Set(INTAKE_FOREIGN_LANGUAGE_OPTIONS.map((option) => option.value));
const KNOWN_AWARD_CATEGORY_VALUES = new Set(INTAKE_AWARD_CATEGORY_OPTIONS.map((option) => option.value));
const KNOWN_DEGREE_VALUES = new Set(INTAKE_ACADEMIC_DEGREE_OPTIONS.map((option) => option.value));
const KNOWN_TITLE_VALUES = new Set(INTAKE_ACADEMIC_TITLE_OPTIONS.map((option) => option.value));

const LEGACY_AWARD_CATEGORY_ALIASES: Record<string, string> = {
  "Государственная награда": "Государственная",
  "Ведомственная награда": "Ведомственная",
  "Юбилейная медаль": "Медаль",
  Другое: INTAKE_AWARD_OTHER,
};

export function intakeAdditionalCellValue(value: string | null | undefined): string {
  const trimmed = String(value ?? "").trim();
  return trimmed || "—";
}

export function emptyIntakeForeignLanguageEntry(): IntakeForeignLanguage {
  return { language: "", proficiency: "" };
}

export function normalizeIntakeForeignLanguageEntry(
  item: Partial<IntakeForeignLanguage> & Record<string, unknown>,
): IntakeForeignLanguage {
  return {
    language: String(item.language ?? ""),
    proficiency: String(item.proficiency ?? ""),
  };
}

export function resolveIntakeForeignLanguageDisplay(language: string): string {
  const trimmed = String(language ?? "").trim();
  if (!trimmed) return "—";
  return trimmed;
}

function resolveAwardCategory(value: string): string {
  const trimmed = String(value ?? "").trim();
  if (!trimmed) return "";
  if (KNOWN_AWARD_CATEGORY_VALUES.has(trimmed)) return trimmed;
  return LEGACY_AWARD_CATEGORY_ALIASES[trimmed] ?? "";
}

export function emptyIntakeAwardEntry(): IntakeAward {
  return { category: "", name: "", issued_by: "", awarded_at: "", document_number: "" };
}

export function normalizeIntakeAwardEntry(item: Partial<IntakeAward> & Record<string, unknown>): IntakeAward {
  let category = resolveAwardCategory(String(item.category ?? ""));
  let name = String(item.name ?? "").trim();
  const legacyTitle = String(item.title ?? "").trim();

  if (!category && !name && legacyTitle) {
    const resolvedCategory = resolveAwardCategory(legacyTitle);
    if (resolvedCategory) {
      category = resolvedCategory;
    } else {
      name = legacyTitle;
    }
  }

  return {
    category,
    name,
    issued_by: String(item.issued_by ?? ""),
    awarded_at: String(item.awarded_at ?? item.date ?? ""),
    document_number: String(item.document_number ?? ""),
  };
}

export function resolveIntakeAwardNameDisplay(award: IntakeAward): string {
  return intakeAdditionalCellValue(normalizeIntakeAwardEntry(award).name);
}

export function resolveIntakeAwardCategoryDisplay(award: IntakeAward): string {
  const normalized = normalizeIntakeAwardEntry(award);
  return intakeAdditionalCellValue(normalized.category);
}

export function emptyIntakeAcademicDegreeEntry(): IntakeAcademicDegree {
  return {
    degree: "",
    degree_other: "",
    field_of_science: "",
    completed_at: "",
    document_number: "",
  };
}

export function emptyIntakeAcademicTitleEntry(): IntakeAcademicTitle {
  return {
    academic_title: "",
    academic_title_other: "",
    field_of_science: "",
    completed_at: "",
    document_number: "",
  };
}

function migrateLegacyCombinedAcademicFields(
  item: Partial<IntakeAcademicDegree & IntakeAcademicTitle> & Record<string, unknown>,
) {
  const label = String(item.label ?? "").trim();
  const degreeType = String(item.degree_type ?? "").trim();
  let degree = String(item.degree ?? "").trim();
  let degreeOther = String(item.degree_other ?? "").trim();
  let fieldOfScience = String(item.field_of_science ?? "").trim();
  let academicTitle = String(item.academic_title ?? "").trim();
  let academicTitleOther = String(item.academic_title_other ?? "").trim();

  if (!degree && !degreeOther && label) {
    if (KNOWN_DEGREE_VALUES.has(label) && label !== INTAKE_ACADEMIC_DEGREE_OTHER) {
      degree = label;
    } else if (KNOWN_TITLE_VALUES.has(label) && label !== INTAKE_ACADEMIC_TITLE_OTHER) {
      academicTitle = label;
    } else {
      degree = INTAKE_ACADEMIC_DEGREE_OTHER;
      degreeOther = label;
    }
  }

  if (!academicTitle && !academicTitleOther && label) {
    for (const option of INTAKE_ACADEMIC_TITLE_OPTIONS) {
      if (option.value !== INTAKE_ACADEMIC_TITLE_OTHER && label.includes(option.value)) {
        academicTitle = option.value;
        break;
      }
    }
  }

  if (!fieldOfScience && degreeType) {
    fieldOfScience = degreeType;
  }

  return {
    degree,
    degreeOther,
    fieldOfScience,
    academicTitle,
    academicTitleOther,
    completedAt: String(item.completed_at ?? ""),
    documentNumber: String(item.document_number ?? ""),
    label,
    degreeType,
  };
}

export function normalizeIntakeAcademicDegreeEntry(
  item: Partial<IntakeAcademicDegree & IntakeAcademicTitle> & Record<string, unknown>,
): IntakeAcademicDegree {
  const migrated = migrateLegacyCombinedAcademicFields(item);
  return {
    degree: migrated.degree,
    degree_other: migrated.degreeOther,
    field_of_science: migrated.fieldOfScience,
    completed_at: migrated.completedAt,
    document_number: migrated.documentNumber,
    ...(migrated.label ? { label: migrated.label } : {}),
    ...(migrated.degreeType ? { degree_type: migrated.degreeType } : {}),
  };
}

export function normalizeIntakeAcademicTitleEntry(
  item: Partial<IntakeAcademicDegree & IntakeAcademicTitle> & Record<string, unknown>,
): IntakeAcademicTitle {
  const migrated = migrateLegacyCombinedAcademicFields(item);
  return {
    academic_title: migrated.academicTitle,
    academic_title_other: migrated.academicTitleOther,
    field_of_science: migrated.fieldOfScience,
    completed_at: migrated.completedAt,
    document_number: migrated.documentNumber,
    ...(migrated.label ? { label: migrated.label } : {}),
    ...(migrated.degreeType ? { degree_type: migrated.degreeType } : {}),
  };
}

function splitLegacyCombinedAcademicEntry(
  item: Partial<IntakeAcademicDegree & IntakeAcademicTitle> & Record<string, unknown>,
): { degrees: IntakeAcademicDegree[]; titles: IntakeAcademicTitle[] } {
  const migrated = migrateLegacyCombinedAcademicFields(item);
  const hasDegree = Boolean(migrated.degree || migrated.degreeOther);
  const hasTitle = Boolean(migrated.academicTitle || migrated.academicTitleOther);
  const shared = {
    field_of_science: migrated.fieldOfScience,
    completed_at: migrated.completedAt,
    document_number: migrated.documentNumber,
    ...(migrated.label ? { label: migrated.label } : {}),
    ...(migrated.degreeType ? { degree_type: migrated.degreeType } : {}),
  };
  const degrees = hasDegree
    ? [
        normalizeIntakeAcademicDegreeEntry({
          degree: migrated.degree,
          degree_other: migrated.degreeOther,
          ...shared,
        }),
      ]
    : [];
  const titles = hasTitle
    ? [
        normalizeIntakeAcademicTitleEntry({
          academic_title: migrated.academicTitle,
          academic_title_other: migrated.academicTitleOther,
          ...shared,
        }),
      ]
    : [];
  return { degrees, titles };
}

export function resolveIntakeAcademicDegreeDisplay(degree: IntakeAcademicDegree): string {
  const normalized = normalizeIntakeAcademicDegreeEntry(degree);
  if (normalized.degree === INTAKE_ACADEMIC_DEGREE_OTHER) {
    return intakeAdditionalCellValue(normalized.degree_other);
  }
  return intakeAdditionalCellValue(normalized.degree);
}

export function resolveIntakeAcademicTitleDisplay(title: IntakeAcademicTitle): string {
  const normalized = normalizeIntakeAcademicTitleEntry(title);
  if (normalized.academic_title === INTAKE_ACADEMIC_TITLE_OTHER) {
    return intakeAdditionalCellValue(normalized.academic_title_other);
  }
  return intakeAdditionalCellValue(normalized.academic_title);
}

export function emptyIntakeAdditionalPayload(): IntakeAdditionalPayload {
  return emptyIntakeDraftPayload().additional;
}

export function normalizeIntakeAdditionalPayload(
  raw: Partial<IntakeAdditionalPayload> | undefined,
): IntakeAdditionalPayload {
  const source = raw ?? {};
  const legacySplitTitles: IntakeAcademicTitle[] = [];
  const academicDegrees = Array.isArray(source.academic_degrees)
    ? source.academic_degrees.flatMap((item) => {
        const split = splitLegacyCombinedAcademicEntry(item);
        legacySplitTitles.push(...split.titles);
        return split.degrees;
      })
    : [];
  const academicTitles = [
    ...legacySplitTitles,
    ...(Array.isArray(source.academic_titles)
      ? source.academic_titles.map((item) => normalizeIntakeAcademicTitleEntry(item))
      : []),
  ];
  return {
    foreign_languages: Array.isArray(source.foreign_languages)
      ? source.foreign_languages.map((item) => normalizeIntakeForeignLanguageEntry(item))
      : [],
    foreign_languages_none: Boolean(source.foreign_languages_none),
    awards: Array.isArray(source.awards) ? source.awards.map((item) => normalizeIntakeAwardEntry(item)) : [],
    awards_none: Boolean(source.awards_none),
    academic_degrees: academicDegrees,
    academic_degrees_none: Boolean(source.academic_degrees_none),
    academic_titles: academicTitles,
    academic_titles_none: Boolean(source.academic_titles_none),
  };
}

export function isIntakeAdditionalSubsectionSettled(items: unknown[], declaredEmpty: boolean): boolean {
  if (declaredEmpty) return true;
  return Array.isArray(items) && items.length > 0;
}

export function formatIntakeAdditionalSubsectionReviewSummary(
  items: unknown[],
  declaredEmpty: boolean,
  formatter: (item: never, index: number) => string,
): string {
  if (declaredEmpty) return "Нет сведений";
  if (!Array.isArray(items) || items.length === 0) return "0 зап.";
  return items.map((item, index) => formatter(item as never, index)).join("; ");
}

export function formatIntakeForeignLanguageReviewLine(item: IntakeForeignLanguage): string {
  const language = resolveIntakeForeignLanguageDisplay(item.language);
  const proficiency = intakeAdditionalCellValue(item.proficiency);
  return `${language} (${proficiency})`;
}

export function formatIntakeAwardReviewLine(item: IntakeAward): string {
  const normalized = normalizeIntakeAwardEntry(item);
  const name = resolveIntakeAwardNameDisplay(normalized);
  const category = resolveIntakeAwardCategoryDisplay(normalized);
  const label = name !== "—" ? name : category;
  const date = formatIntakeDateForDisplay(normalized.awarded_at, "period") || "—";
  return `${label}, ${date}`;
}

export function formatIntakeAcademicDegreeReviewLine(item: IntakeAcademicDegree): string {
  const normalized = normalizeIntakeAcademicDegreeEntry(item);
  const summary = resolveIntakeAcademicDegreeDisplay(normalized);
  const date = formatIntakeDateForDisplay(normalized.completed_at, "period") || "—";
  return `${summary}, ${date}`;
}

export function formatIntakeAcademicTitleReviewLine(item: IntakeAcademicTitle): string {
  const normalized = normalizeIntakeAcademicTitleEntry(item);
  const summary = resolveIntakeAcademicTitleDisplay(normalized);
  const date = formatIntakeDateForDisplay(normalized.completed_at, "period") || "—";
  return `${summary}, ${date}`;
}

export function formatIntakeAwardDateCell(value: string | null | undefined): string {
  const formatted = formatIntakeDateForDisplay(value, "period");
  return formatted || "—";
}

export function formatIntakeAcademicDegreeDateCell(value: string | null | undefined): string {
  const formatted = formatIntakeDateForDisplay(value, "period");
  return formatted || "—";
}

export function parseIntakeForeignLanguageFocusRowIndex(focusTestId: string | null | undefined): number | null {
  const match = String(focusTestId ?? "").match(/^intake-foreign-language-(?:language|proficiency)-(\d+)$/);
  return match ? Number(match[1]) : null;
}

export function parseIntakeAwardFocusRowIndex(focusTestId: string | null | undefined): number | null {
  const match = String(focusTestId ?? "").match(
    /^intake-award-(?:category|name|issued-by|awarded-at|document-number)-(\d+)$/,
  );
  return match ? Number(match[1]) : null;
}

export function parseIntakeAcademicDegreeFocusRowIndex(focusTestId: string | null | undefined): number | null {
  const match = String(focusTestId ?? "").match(
    /^intake-academic-degree-(?:degree|degree-other|field-of-science|completed-at|document-number)-(\d+)$/,
  );
  return match ? Number(match[1]) : null;
}

export function parseIntakeAcademicTitleFocusRowIndex(focusTestId: string | null | undefined): number | null {
  const match = String(focusTestId ?? "").match(
    /^intake-academic-title-(?:academic-title|academic-title-other|field-of-science|completed-at|document-number)-(\d+)$/,
  );
  return match ? Number(match[1]) : null;
}

export function isKnownIntakeForeignLanguageOption(value: string): boolean {
  return KNOWN_LANGUAGE_VALUES.has(value);
}

export function isKnownIntakeAwardCategory(value: string): boolean {
  return KNOWN_AWARD_CATEGORY_VALUES.has(value);
}

export {
  INTAKE_FOREIGN_LANGUAGE_OTHER,
  INTAKE_AWARD_OTHER,
  INTAKE_ACADEMIC_DEGREE_OTHER,
  INTAKE_ACADEMIC_TITLE_OTHER,
};
