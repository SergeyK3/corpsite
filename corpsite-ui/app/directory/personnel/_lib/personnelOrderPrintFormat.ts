import type { PersonnelOrderPrintLanguage } from "./personnelOrderPrintLanguage";
import { PERSONNEL_ORDER_PRINT_DICTIONARIES } from "./personnelOrderPrintLocale";

const RU_MONTHS = [
  "января",
  "февраля",
  "марта",
  "апреля",
  "мая",
  "июня",
  "июля",
  "августа",
  "сентября",
  "октября",
  "ноября",
  "декабря",
] as const;

const KK_MONTHS = [
  "қаңтар",
  "ақпан",
  "наурыз",
  "сәуір",
  "мамыр",
  "маусым",
  "шілде",
  "тамыз",
  "қыркүйек",
  "қазан",
  "қараша",
  "желтоқсан",
] as const;

export type CalendarDateParts = { year: number; month: number; day: number };

/** Parse YYYY-MM-DD without timezone shift. */
export function parsePersonnelOrderCalendarDate(
  value: string | null | undefined,
): CalendarDateParts | null {
  const raw = String(value || "").trim();
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(raw);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (!Number.isFinite(year) || !Number.isFinite(month) || !Number.isFinite(day)) return null;
  if (month < 1 || month > 12 || day < 1 || day > 31) return null;
  return { year, month, day };
}

function formatDateRu(parts: CalendarDateParts): string {
  return `${parts.day} ${RU_MONTHS[parts.month - 1]} ${parts.year} года`;
}

function formatDateKk(parts: CalendarDateParts): string {
  return `${parts.year} жылғы ${parts.day} ${KK_MONTHS[parts.month - 1]}`;
}

export function formatPersonnelOrderPrintDate(
  value: string | null | undefined,
  language: PersonnelOrderPrintLanguage | "kk" | "ru",
): string {
  const parts = parsePersonnelOrderCalendarDate(value);
  if (!parts) {
    const fallback = String(value || "").trim();
    return fallback || "—";
  }
  if (language === "kk") return formatDateKk(parts);
  if (language === "ru") return formatDateRu(parts);
  // kk-ru caller should format per line; default to ru for single-string helper
  return formatDateRu(parts);
}

export function formatPersonnelOrderPrintDateLines(
  value: string | null | undefined,
  language: PersonnelOrderPrintLanguage,
): string[] {
  const parts = parsePersonnelOrderCalendarDate(value);
  if (!parts) {
    const fallback = String(value || "").trim();
    return fallback ? [fallback] : ["—"];
  }
  if (language === "kk") return [formatDateKk(parts)];
  if (language === "ru") return [formatDateRu(parts)];
  return [formatDateKk(parts), formatDateRu(parts)];
}

/** Numeric rate only, e.g. "1,0" — no unit word. */
export function formatPersonnelOrderPrintRateValue(
  rate: number | string | null | undefined,
): string {
  if (rate == null || rate === "") return "—";
  const numeric = typeof rate === "number" ? rate : Number(String(rate).replace(",", "."));
  if (!Number.isFinite(numeric)) {
    const raw = String(rate).trim();
    return raw || "—";
  }
  return numeric.toLocaleString("ru-RU", {
    minimumFractionDigits: Number.isInteger(numeric) ? 1 : 0,
    maximumFractionDigits: 2,
  });
}

export function formatPersonnelOrderPrintRate(
  rate: number | string | null | undefined,
  language: PersonnelOrderPrintLanguage | "kk" | "ru",
): string {
  const formatted = formatPersonnelOrderPrintRateValue(rate);
  if (formatted === "—") return formatted;
  const unit =
    language === "kk"
      ? PERSONNEL_ORDER_PRINT_DICTIONARIES.kk.rateUnit
      : PERSONNEL_ORDER_PRINT_DICTIONARIES.ru.rateUnit;
  return `${formatted} ${unit}`;
}

export function formatPersonnelOrderPrintRateLines(
  rate: number | string | null | undefined,
  language: PersonnelOrderPrintLanguage,
): string[] {
  if (language === "kk-ru") {
    return [
      formatPersonnelOrderPrintRate(rate, "kk"),
      formatPersonnelOrderPrintRate(rate, "ru"),
    ];
  }
  return [formatPersonnelOrderPrintRate(rate, language)];
}
