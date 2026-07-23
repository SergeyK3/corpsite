import {
  INTAKE_EDUCATION_DOCUMENT_TYPE_OPTIONS,
  INTAKE_EDUCATION_TYPE_OPTIONS,
  type IntakeEducation,
  type IntakeEducationDocumentType,
} from "./intakeApi.client";
import { formatIntakePeriodForDisplay, formatIntakePeriodRange } from "./intakePeriodFormat";

export type IntakeEducationRow = {
  item: IntakeEducation;
  index: number;
};

const EDUCATION_DOCUMENT_TYPES = new Set<IntakeEducationDocumentType>(
  INTAKE_EDUCATION_DOCUMENT_TYPE_OPTIONS.map((option) => option.value),
);

export function normalizeIntakeEducationDocumentType(
  raw: string | null | undefined,
): IntakeEducationDocumentType {
  const value = String(raw ?? "").trim().toLowerCase();
  if (EDUCATION_DOCUMENT_TYPES.has(value as IntakeEducationDocumentType)) {
    return value as IntakeEducationDocumentType;
  }
  return "diploma";
}

export function normalizeIntakeEducationEntry(
  item: Partial<IntakeEducation> & Record<string, unknown>,
): IntakeEducation {
  return {
    education_type: (item.education_type as IntakeEducation["education_type"]) ?? "basic",
    institution: String(item.institution ?? ""),
    year_from: String(item.year_from ?? ""),
    year_to: String(item.year_to ?? ""),
    specialty: String(item.specialty ?? ""),
    qualification: String(item.qualification ?? ""),
    document_type: normalizeIntakeEducationDocumentType(String(item.document_type ?? "")),
    diploma_number: String(item.diploma_number ?? ""),
  };
}

export function emptyIntakeEducationEntry(): IntakeEducation {
  return normalizeIntakeEducationEntry({});
}

export function intakeEducationCellValue(value: string | null | undefined): string {
  const trimmed = String(value ?? "").trim();
  return trimmed || "—";
}

export function formatIntakeEducationPeriodCell(
  yearFrom: string | null | undefined,
  yearTo: string | null | undefined,
): string {
  const from = formatIntakePeriodForDisplay(yearFrom);
  const to = formatIntakePeriodForDisplay(yearTo);
  if (!from && !to) return "—";
  return formatIntakePeriodRange(yearFrom, yearTo);
}

export function formatIntakeEducationSpecialtyCell(
  specialty: string | null | undefined,
  qualification: string | null | undefined,
): string {
  const specialtyValue = String(specialty ?? "").trim();
  const qualificationValue = String(qualification ?? "").trim();
  if (specialtyValue && qualificationValue) {
    return `${specialtyValue} / ${qualificationValue}`;
  }
  return specialtyValue || qualificationValue || "—";
}

export function getIntakeEducationTypeLabel(value: IntakeEducation["education_type"]): string {
  return INTAKE_EDUCATION_TYPE_OPTIONS.find((option) => option.value === value)?.label ?? value;
}

export function getIntakeEducationDocumentTypeLabel(
  value: IntakeEducationDocumentType | string | null | undefined,
): string {
  const normalized = normalizeIntakeEducationDocumentType(value);
  return (
    INTAKE_EDUCATION_DOCUMENT_TYPE_OPTIONS.find((option) => option.value === normalized)?.label ??
    normalized
  );
}

function educationStartSortKey(raw: string | null | undefined): string {
  return String(raw ?? "").trim();
}

export function sortIntakeEducationRows(items: readonly IntakeEducation[]): IntakeEducationRow[] {
  return items
    .map((item, index) => ({ item, index }))
    .sort((left, right) => {
      const leftKey = educationStartSortKey(left.item.year_from);
      const rightKey = educationStartSortKey(right.item.year_from);
      if (leftKey === rightKey) return left.index - right.index;
      if (!leftKey) return 1;
      if (!rightKey) return -1;
      return rightKey.localeCompare(leftKey);
    });
}

export function parseIntakeEducationFocusRowIndex(focusTestId: string | null | undefined): number | null {
  if (!focusTestId) return null;
  const match = focusTestId.match(/^intake-education-year-(?:from|to)-(\d+)$/);
  return match ? Number(match[1]) : null;
}
