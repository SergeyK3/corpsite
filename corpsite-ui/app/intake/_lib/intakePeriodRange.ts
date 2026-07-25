import { parsePersonnelDayDateInput } from "@/lib/personnelDayDate";
import { isIncompleteIntakePeriodDate, isValidIntakeFullDateIso } from "./intakeDateValidation";

export const INTAKE_PERIOD_RANGE_ERROR = "Дата окончания не может быть раньше даты начала";

function normalizeIntakePeriodDateForRange(raw: string | null | undefined): string {
  const text = String(raw ?? "").trim();
  if (!text) return "";
  const parsed = parsePersonnelDayDateInput(text);
  return isValidIntakeFullDateIso(parsed) ? parsed : text;
}

export function countInclusiveCalendarDays(fromIso: string, toIso: string): number | null {
  if (!isValidIntakeFullDateIso(fromIso) || !isValidIntakeFullDateIso(toIso)) {
    return null;
  }
  const fromParts = fromIso.slice(0, 10).split("-").map(Number);
  const toParts = toIso.slice(0, 10).split("-").map(Number);
  const fromDate = Date.UTC(fromParts[0], fromParts[1] - 1, fromParts[2]);
  const toDate = Date.UTC(toParts[0], toParts[1] - 1, toParts[2]);
  if (fromDate > toDate) return null;
  return Math.floor((toDate - fromDate) / 86_400_000) + 1;
}

export function resolveIntakePeriodRangeError(
  fromRaw: string | null | undefined,
  toRaw: string | null | undefined,
): string | null {
  const from = normalizeIntakePeriodDateForRange(fromRaw);
  const to = normalizeIntakePeriodDateForRange(toRaw);
  if (!from || !to) return null;
  if (isIncompleteIntakePeriodDate(from) || isIncompleteIntakePeriodDate(to)) return null;
  if (countInclusiveCalendarDays(from, to) === null) return INTAKE_PERIOD_RANGE_ERROR;
  return null;
}

export function isInvalidIntakePeriodRange(
  fromRaw: string | null | undefined,
  toRaw: string | null | undefined,
): boolean {
  return resolveIntakePeriodRangeError(fromRaw, toRaw) !== null;
}
