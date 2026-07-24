export const INTAKE_PDF_TIMEZONE = "Asia/Almaty";

/**
 * Formats the PDF generation date as dd.mm.yyyy in Asia/Almaty.
 */
export function formatIntakePdfGeneratedDate(now: Date = new Date()): string {
  const formatter = new Intl.DateTimeFormat("ru-RU", {
    timeZone: INTAKE_PDF_TIMEZONE,
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
  const parts = formatter.formatToParts(now);
  const day = parts.find((part) => part.type === "day")?.value ?? "01";
  const month = parts.find((part) => part.type === "month")?.value ?? "01";
  const year = parts.find((part) => part.type === "year")?.value ?? "1970";
  return `${day}.${month}.${year}`;
}

export function buildIntakePdfGeneratedDateLabel(now: Date = new Date()): string {
  return `Дата формирования: ${formatIntakePdfGeneratedDate(now)}`;
}

/** Canonical as-of date (YYYY-MM-DD) in Asia/Almaty for PDF calculations. */
export function formatIntakePdfAsOfIso(now: Date = new Date()): string {
  const formatter = new Intl.DateTimeFormat("en-CA", {
    timeZone: INTAKE_PDF_TIMEZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  return formatter.format(now);
}

export function formatIntakePdfCalculationDateLabel(asOfIso: string): string {
  const [year, month, day] = asOfIso.split("-");
  if (!year || !month || !day) return asOfIso;
  return `${day}.${month}.${year}`;
}
