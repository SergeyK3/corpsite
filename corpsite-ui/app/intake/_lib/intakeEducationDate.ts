import { formatPersonnelDate, parsePersonnelDateInput } from "@/lib/personnelDateFormat";
import { isValidPersonnelDayDateIso } from "@/lib/personnelDayDate";

export function parseIntakeEducationDate(input: string): string {
  const text = input.trim();
  if (/^\d{4}$/.test(text)) return text;
  if (/^\d{8}$/.test(text)) {
    const parsed = parsePersonnelDateInput(`${text.slice(0, 2)}.${text.slice(2, 4)}.${text.slice(4)}`, "day");
    return isValidPersonnelDayDateIso(parsed) ? parsed : text;
  }
  const parsed = parsePersonnelDateInput(text, "day");
  return isValidPersonnelDayDateIso(parsed) ? parsed : text;
}

export function isIncompleteIntakeEducationDate(value: string | null | undefined): boolean {
  const text = String(value ?? "").trim();
  if (!text) return false;
  if (/^\d{4}$/.test(text)) return Number(text) < 1000 || Number(text) > 9999;
  return !isValidPersonnelDayDateIso(parseIntakeEducationDate(text));
}

export function formatIntakeEducationDate(value: string | null | undefined): string {
  const text = String(value ?? "").trim();
  if (!text || /^\d{4}$/.test(text)) return text;
  const parsed = parseIntakeEducationDate(text);
  return isValidPersonnelDayDateIso(parsed)
    ? formatPersonnelDate(parsed, { precision: "day", empty: "" })
    : text;
}

export function formatIntakeEducationPeriod(fromRaw: string | null | undefined, toRaw: string | null | undefined): string {
  const from = formatIntakeEducationDate(fromRaw);
  const to = formatIntakeEducationDate(toRaw);
  if (!from && !to) return "—";
  if (from && to) return /^\d{4}$/.test(from) && /^\d{4}$/.test(to)
    ? `${from}–${to}`
    : `${from} — ${to}`;
  return from || to;
}

export function resolveIntakeEducationPeriodError(fromRaw: string | null | undefined, toRaw: string | null | undefined): string | null {
  const from = String(fromRaw ?? "").trim();
  const to = String(toRaw ?? "").trim();
  if (!from || !to || isIncompleteIntakeEducationDate(from) || isIncompleteIntakeEducationDate(to)) return null;
  const fromKey = /^\d{4}$/.test(from) ? `${from}-01-01` : parseIntakeEducationDate(from);
  const toKey = /^\d{4}$/.test(to) ? `${to}-12-31` : parseIntakeEducationDate(to);
  return fromKey > toKey ? "Дата окончания не может быть раньше даты начала" : null;
}
