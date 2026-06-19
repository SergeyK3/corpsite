// ADR-040 Phase G — materialized HR change event labels and display helpers.

import { getMonthlyDiffFieldLabel } from "./monthlyDiffLabels";

export type HrChangeEventType =
  | "NEW"
  | "REMOVED"
  | "POSITION_CHANGED"
  | "DEPARTMENT_CHANGED"
  | "EDUCATION_CHANGED"
  | "CERTIFICATE_CHANGED";

export const HR_CHANGE_EVENT_TYPES: readonly HrChangeEventType[] = [
  "NEW",
  "REMOVED",
  "POSITION_CHANGED",
  "DEPARTMENT_CHANGED",
  "EDUCATION_CHANGED",
  "CERTIFICATE_CHANGED",
] as const;

export const HR_CHANGE_EVENT_TYPE_LABELS: Record<HrChangeEventType, string> = {
  NEW: "Новый сотрудник",
  REMOVED: "Отсутствует в новом файле / возможно уволен",
  POSITION_CHANGED: "Изменилась должность",
  DEPARTMENT_CHANGED: "Изменилось отделение",
  EDUCATION_CHANGED: "Изменилось образование",
  CERTIFICATE_CHANGED: "Изменился сертификат",
};

export const HR_CHANGE_EVENT_FILTER_OPTIONS: ReadonlyArray<{ value: "" | HrChangeEventType; label: string }> = [
  { value: "", label: "Все типы" },
  ...HR_CHANGE_EVENT_TYPES.map((value) => ({
    value,
    label: HR_CHANGE_EVENT_TYPE_LABELS[value],
  })),
];

export function isHrChangeEventType(value: string | null | undefined): value is HrChangeEventType {
  return Boolean(value && (HR_CHANGE_EVENT_TYPES as readonly string[]).includes(value));
}

export function hrChangeEventTypeLabel(eventType: string | null | undefined): string {
  const normalized = String(eventType || "").trim().toUpperCase();
  if (isHrChangeEventType(normalized)) {
    return HR_CHANGE_EVENT_TYPE_LABELS[normalized];
  }
  return normalized || "—";
}

export function hrChangeEventBadgeClass(eventType: HrChangeEventType): string {
  switch (eventType) {
    case "NEW":
      return "border-blue-200 bg-blue-100 text-blue-900 dark:border-blue-800 dark:bg-blue-950/50 dark:text-blue-200";
    case "REMOVED":
      return "border-red-200 bg-red-100 text-red-900 dark:border-red-800 dark:bg-red-950/50 dark:text-red-200";
    case "POSITION_CHANGED":
      return "border-violet-200 bg-violet-100 text-violet-900 dark:border-violet-800 dark:bg-violet-950/50 dark:text-violet-200";
    case "DEPARTMENT_CHANGED":
      return "border-cyan-200 bg-cyan-100 text-cyan-900 dark:border-cyan-800 dark:bg-cyan-950/50 dark:text-cyan-200";
    case "EDUCATION_CHANGED":
      return "border-amber-200 bg-amber-100 text-amber-900 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-200";
    case "CERTIFICATE_CHANGED":
      return "border-orange-200 bg-orange-100 text-orange-900 dark:border-orange-800 dark:bg-orange-950/50 dark:text-orange-200";
    default:
      return "border-zinc-200 bg-zinc-100 text-zinc-700 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300";
  }
}

export function hrChangeEventFieldLabel(fieldName: string | null | undefined, recordKind?: string | null): string {
  const field = String(fieldName || "").trim();
  if (!field) return "—";
  return getMonthlyDiffFieldLabel(field, recordKind || undefined);
}

export function formatHrChangeEventValue(value: string | null | undefined): string {
  const text = String(value ?? "").trim();
  return text || "—";
}

export function formatHrChangeEventDate(value: string | null | undefined): string {
  if (!value) return "—";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return value;
  return dt.toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" });
}
