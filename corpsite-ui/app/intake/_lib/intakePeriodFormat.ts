import {
  formatPersonnelDate,
  formatPersonnelDateRange,
  parsePersonnelDateInput,
  type PersonnelDatePrecision,
} from "@/lib/personnelDateFormat";

export type IntakePeriodPrecision = Exclude<PersonnelDatePrecision, "month" | "auto">;

export function formatIntakePeriodForDisplay(
  raw: string | null | undefined,
  precision: IntakePeriodPrecision,
): string {
  return formatPersonnelDate(raw, { precision, empty: "" });
}

export function parseIntakePeriodInput(input: string, precision: IntakePeriodPrecision): string {
  return parsePersonnelDateInput(input, precision);
}

export function formatIntakePeriodRange(
  fromRaw: string | null | undefined,
  toRaw: string | null | undefined,
  precision: IntakePeriodPrecision = "year",
): string {
  return formatPersonnelDateRange(fromRaw, toRaw, { precision, empty: "—" });
}

export function formatIntakeEducationReviewLine(item: {
  institution?: string;
  year_from?: string;
  year_to?: string;
}): string {
  const title = String(item.institution ?? "").trim() || "—";
  const period = formatIntakePeriodRange(item.year_from, item.year_to, "year");
  return `${title}: ${period}`;
}

export function formatIntakeTrainingReviewLine(item: {
  institution?: string;
  course_name?: string;
  year?: string;
}): string {
  const title = String(item.course_name ?? item.institution ?? "").trim() || "—";
  const year = formatIntakePeriodForDisplay(item.year, "year");
  return year ? `${title} (${year})` : title;
}
