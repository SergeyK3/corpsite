// ADR-040 Phase C — monthly diff status labels and field display helpers.

import { getNormalizedRecordKindLabel } from "./normalizedRecordLabels";

import { NORMALIZED_RECORD_KIND_LABELS, type NormalizedRecordKind } from "./normalizedRecordLabels";

export type MonthlyDiffStatus = "UNCHANGED" | "NEW" | "CHANGED" | "REMOVED" | "CONFLICT";

export const MONTHLY_DIFF_STATUSES: readonly MonthlyDiffStatus[] = [
  "UNCHANGED",
  "NEW",
  "CHANGED",
  "REMOVED",
  "CONFLICT",
] as const;

export const MONTHLY_DIFF_STATUS_LABELS: Record<MonthlyDiffStatus, string> = {
  UNCHANGED: "Без изменений",
  NEW: "Новая",
  CHANGED: "Изменена",
  REMOVED: "Удалена из файла",
  CONFLICT: "Конфликт",
};

export const MONTHLY_DIFF_STATUS_SUMMARY_LABELS: Record<MonthlyDiffStatus, string> = {
  UNCHANGED: "Без изменений",
  NEW: "Новые",
  CHANGED: "Изменённые",
  REMOVED: "Отсутствуют в файле",
  CONFLICT: "Конфликты",
};

export function isMonthlyDiffStatus(value: string | null | undefined): value is MonthlyDiffStatus {
  return Boolean(value && (MONTHLY_DIFF_STATUSES as readonly string[]).includes(value));
}

export const REVIEW_EXCEPTION_STATUSES: readonly MonthlyDiffStatus[] = [
  "NEW",
  "CHANGED",
  "CONFLICT",
  "REMOVED",
] as const;

export function isReviewExceptionStatus(
  value: string | null | undefined,
): value is MonthlyDiffStatus {
  return Boolean(value && (REVIEW_EXCEPTION_STATUSES as readonly string[]).includes(value));
}

export function monthlyDiffStatusBadgeClass(status: MonthlyDiffStatus): string {
  switch (status) {
    case "UNCHANGED":
      return "border-zinc-200 bg-zinc-100 text-zinc-700 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300";
    case "NEW":
      return "border-blue-200 bg-blue-100 text-blue-900 dark:border-blue-800 dark:bg-blue-950/50 dark:text-blue-200";
    case "CHANGED":
      return "border-amber-200 bg-amber-100 text-amber-900 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-200";
    case "REMOVED":
      return "border-red-200 bg-red-100 text-red-900 dark:border-red-800 dark:bg-red-950/50 dark:text-red-200";
    case "CONFLICT":
      return "border-orange-200 bg-orange-100 text-orange-900 dark:border-orange-800 dark:bg-orange-950/50 dark:text-orange-200";
    default:
      return "border-zinc-200 bg-zinc-100 text-zinc-700";
  }
}

export type FieldDiffEntry = {
  canonical: unknown;
  incoming: unknown;
};

export type MonthlyDiffFields = {
  diff_status?: MonthlyDiffStatus | null;
  canonical_snapshot_id?: number | null;
  canonical_entry_id?: number | null;
  canonical_hash?: string | null;
  field_diffs?: Record<string, FieldDiffEntry> | null;
  diff_computed_at?: string | null;
};

const ROSTER_FIELD_LABELS: Record<string, string> = {
  full_name: "ФИО",
  iin: "ИИН",
  birth_date: "Дата рождения",
  department: "Отделение",
  org_unit_id: "ID подразделения",
  position_raw: "Должность",
  training_raw: "Обучение (сырой текст)",
  certification_raw: "Категория / сертификация",
  education_raw: "Образование (сырой текст)",
  degree_raw: "Учёная степень",
  experience_raw: "Стаж",
  note_raw: "Примечание",
};

const NORMALIZED_FIELD_LABELS: Record<string, string> = {
  title: "Название",
  provider: "Организация",
  hours: "Часы",
  start_date: "Дата начала",
  end_date: "Дата окончания",
  issue_date: "Дата выдачи",
  expiry_date: "Дата окончания действия",
  document_number: "Номер документа",
  specialty_text: "Специальность",
  medical_specialty_id: "ID специальности",
  file_url: "Ссылка на файл",
  record_kind: "Тип записи",
};

export function getMonthlyDiffFieldLabel(field: string, recordKind?: string | null): string {
  if (field === "record_kind" && recordKind && recordKind in NORMALIZED_RECORD_KIND_LABELS) {
    return "Тип записи";
  }
  if (recordKind && recordKind !== "roster" && NORMALIZED_FIELD_LABELS[field]) {
    return NORMALIZED_FIELD_LABELS[field];
  }
  return ROSTER_FIELD_LABELS[field] || NORMALIZED_FIELD_LABELS[field] || field;
}

export function formatMonthlyDiffValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "Да" : "Нет";
  if (typeof value === "number") return String(value);
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

export function formatReviewExceptionFieldValue(
  field: { value?: string | null; display_value?: string | null },
): string {
  const display = field.display_value ?? field.value;
  return formatMonthlyDiffValue(display);
}

export function formatReviewExceptionDiffValue(
  side: "baseline" | "import",
  row: {
    baseline_value?: string | null;
    baseline_display_value?: string | null;
    import_value?: string | null;
    import_display_value?: string | null;
  },
): string {
  if (side === "baseline") {
    return formatMonthlyDiffValue(row.baseline_display_value ?? row.baseline_value);
  }
  return formatMonthlyDiffValue(row.import_display_value ?? row.import_value);
}

const RECORD_KIND_DISPLAY: Record<string, string> = {
  training: "Обучение",
  education: "Образование",
  certificate: "Сертификат",
  category: "Категория",
  roster: "Состав",
};

export function formatMonthlyDiffFieldDisplayValue(
  field: string,
  value: unknown,
  recordKind?: string | null,
): string {
  if (value === null || value === undefined || value === "") return "—";
  if (field === "record_kind") {
    const raw = String(value);
    return RECORD_KIND_DISPLAY[raw] || getNormalizedRecordKindLabel(raw, raw);
  }
  return formatMonthlyDiffValue(value);
}

export function removedEntryTitle(payload: Record<string, unknown> | null | undefined): string {
  const data = payload ?? {};
  const fullName = String(data.full_name ?? "").trim();
  if (fullName) return fullName;
  const title = String(data.title ?? "").trim();
  if (title) return title;
  return "—";
}

export function removedEntrySubtitle(
  payload: Record<string, unknown> | null | undefined,
  recordKind: string
): string {
  const data = payload ?? {};
  const parts: string[] = [];
  if (recordKind && recordKind !== "roster") {
    const kind = recordKind as NormalizedRecordKind;
    if (kind in NORMALIZED_RECORD_KIND_LABELS) {
      parts.push(NORMALIZED_RECORD_KIND_LABELS[kind]);
    } else {
      parts.push(recordKind);
    }
  }
  const iin = String(data.iin ?? "").trim();
  if (iin) parts.push(`ИИН ${iin}`);
  const position = String(data.position_raw ?? "").trim();
  if (position) parts.push(position);
  const department = String(data.department ?? "").trim();
  if (department) parts.push(department);
  return parts.join(" · ") || "—";
}
