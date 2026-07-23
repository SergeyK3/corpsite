import {
  formatIntakeDateForDisplay,
  INTAKE_INCOMPLETE_DATE_REVIEW_SUFFIX,
} from "./intakeDateValidation";
import {
  formatPersonnelDateRange,
  parsePersonnelDateInput,
} from "@/lib/personnelDateFormat";

export function formatIntakePeriodForDisplay(raw: string | null | undefined): string {
  return formatIntakeDateForDisplay(raw, "period");
}

export function formatIntakeBirthDateForDisplay(raw: string | null | undefined): string {
  return formatIntakeDateForDisplay(raw, "birth");
}

export function parseIntakePeriodInput(input: string): string {
  return parsePersonnelDateInput(input, "day");
}

export function formatIntakePeriodRange(
  fromRaw: string | null | undefined,
  toRaw: string | null | undefined,
): string {
  const from = formatIntakePeriodForDisplay(fromRaw);
  const to = formatIntakePeriodForDisplay(toRaw);
  if (!from && !to) return "—";
  if (from && to) return `${from} — ${to}`;
  return from || to;
}

export function formatIntakeEducationReviewLine(item: {
  institution?: string;
  year_from?: string;
  year_to?: string;
}): string {
  const title = String(item.institution ?? "").trim() || "—";
  const period = formatIntakePeriodRange(item.year_from, item.year_to);
  return `${title}: ${period}`;
}

export function formatIntakeTrainingReviewLine(item: {
  institution?: string;
  course_name?: string;
  year?: string;
}): string {
  const title = String(item.course_name ?? item.institution ?? "").trim() || "—";
  const dateLabel = formatIntakePeriodForDisplay(item.year);
  if (!dateLabel) return title;
  if (dateLabel.includes(INTAKE_INCOMPLETE_DATE_REVIEW_SUFFIX)) {
    return `${title} (${dateLabel})`;
  }
  return `${title} (${dateLabel})`;
}

export function formatIntakeRelativeReviewLine(item: {
  full_name?: string;
  birth_year?: string;
}): string {
  const name = String(item.full_name ?? "").trim() || "—";
  const birthDate = formatIntakePeriodForDisplay(item.birth_year);
  return birthDate ? `${name}, ${birthDate}` : name;
}

export function formatIntakeEmploymentReviewLine(item: {
  organization?: string;
  position?: string;
  year_from?: string;
  year_to?: string;
}): string {
  const org = String(item.organization ?? "").trim() || "—";
  const position = String(item.position ?? "").trim();
  const period = formatIntakePeriodRange(item.year_from, item.year_to);
  const title = position ? `${org} — ${position}` : org;
  return `${title}: ${period}`;
}
