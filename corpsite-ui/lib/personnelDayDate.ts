import { formatPersonnelDate, parsePersonnelDateInput } from "@/lib/personnelDateFormat";

export const PERSONNEL_DAY_DATE_PLACEHOLDER = "ДД.ММ.ГГГГ";
export const PERSONNEL_INCOMPLETE_DATE_HINT = "Укажите полную дату в формате ДД.ММ.ГГГГ";
export const PERSONNEL_INCOMPLETE_DATE_SUFFIX = "(уточните дату)";

const ISO_DATE_RE = /^(\d{4})-(\d{2})-(\d{2})$/;
const YEAR_RE = /^\d{4}$/;
const PARTIAL_YEAR_RE = /^\d{1,3}$/;
const LEGACY_YEAR_ONLY_DDMMYYYY_RE = /^01\.01\.\d{4}$/;

export type PersonnelDayDateMode = "document" | "birth";

function normalizeText(value: string | null | undefined): string {
  return String(value ?? "").trim();
}

function isYearOnlyIsoDate(text: string): boolean {
  const match = ISO_DATE_RE.exec(text);
  if (!match) return false;
  return match[2] === "01" && match[3] === "01";
}

/** True when value is a complete calendar date stored as YYYY-MM-DD. */
export function isValidPersonnelDayDateIso(value: string | null | undefined): boolean {
  const text = normalizeText(value);
  if (!text || !ISO_DATE_RE.test(text)) return false;
  const [year, month, day] = text.split("-").map(Number);
  const candidate = new Date(year, month - 1, day);
  return (
    candidate.getFullYear() === year &&
    candidate.getMonth() === month - 1 &&
    candidate.getDate() === day
  );
}

/** Legacy placeholder 01.01.YYYY in display format. */
export function isLegacyYearOnlyDocumentDate(value: string | null | undefined): boolean {
  return LEGACY_YEAR_ONLY_DDMMYYYY_RE.test(normalizeText(value));
}

/** Incomplete legacy or in-progress document/category/certificate dates. */
export function isIncompletePersonnelDocumentDate(value: string | null | undefined): boolean {
  const text = normalizeText(value);
  if (!text) return false;
  if (PARTIAL_YEAR_RE.test(text) || YEAR_RE.test(text)) return true;
  if (isLegacyYearOnlyDocumentDate(text)) return true;
  if (ISO_DATE_RE.test(text)) return isYearOnlyIsoDate(text);
  return !isValidPersonnelDayDateIso(parsePersonnelDayDateInput(text));
}

/** Incomplete birth-style dates where January 1 remains valid. */
export function isIncompletePersonnelBirthDate(value: string | null | undefined): boolean {
  const text = normalizeText(value);
  if (!text) return false;
  if (PARTIAL_YEAR_RE.test(text) || YEAR_RE.test(text)) return true;
  return !isValidPersonnelDayDateIso(parsePersonnelDayDateInput(text));
}

export function isIncompletePersonnelDayDate(
  value: string | null | undefined,
  mode: PersonnelDayDateMode = "document",
): boolean {
  return mode === "birth"
    ? isIncompletePersonnelBirthDate(value)
    : isIncompletePersonnelDocumentDate(value);
}

export function formatPersonnelDayDateForDisplay(
  value: string | null | undefined,
  mode: PersonnelDayDateMode = "document",
): string {
  const text = normalizeText(value);
  if (!text) return "";
  if (text.toLowerCase() === "постоянно") return text;

  if (isIncompletePersonnelDayDate(text, mode)) {
    if (YEAR_RE.test(text)) return `${text} ${PERSONNEL_INCOMPLETE_DATE_SUFFIX}`;
    if (PARTIAL_YEAR_RE.test(text)) return `${text} ${PERSONNEL_INCOMPLETE_DATE_SUFFIX}`;
    if (ISO_DATE_RE.test(text) && mode === "document" && isYearOnlyIsoDate(text)) {
      return `${text.slice(0, 4)} ${PERSONNEL_INCOMPLETE_DATE_SUFFIX}`;
    }
    const parsed = parsePersonnelDayDateInput(text);
    if (parsed && isIncompletePersonnelDayDate(parsed, mode)) {
      return `${formatPersonnelDate(parsed, { precision: "day", empty: "" })} ${PERSONNEL_INCOMPLETE_DATE_SUFFIX}`;
    }
    return `${text} ${PERSONNEL_INCOMPLETE_DATE_SUFFIX}`;
  }

  const canonical = parsePersonnelDayDateInput(text);
  return formatPersonnelDate(canonical || text, { precision: "day", empty: "" });
}

export function parsePersonnelDayDateInput(input: string): string {
  return parsePersonnelDateInput(input, "day");
}

/** Normalize user input to canonical ISO when complete; preserve legacy incomplete values. */
export function normalizePersonnelDocumentDateInput(value: string): string {
  const text = normalizeText(value);
  if (!text) return "";
  if (text.toLowerCase() === "постоянно") return text;
  const parsed = parsePersonnelDayDateInput(text);
  if (isValidPersonnelDayDateIso(parsed)) return parsed;
  return text;
}

export function validatePersonnelDocumentDate(value: string): string | null {
  const text = normalizeText(value);
  if (!text) return null;
  if (text.toLowerCase() === "постоянно") return null;
  if (isIncompletePersonnelDocumentDate(text)) return PERSONNEL_INCOMPLETE_DATE_HINT;
  if (isValidPersonnelDayDateIso(parsePersonnelDayDateInput(text))) return null;
  return PERSONNEL_INCOMPLETE_DATE_HINT;
}
