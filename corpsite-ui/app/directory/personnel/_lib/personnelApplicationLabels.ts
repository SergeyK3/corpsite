export const PERSONNEL_APPLICATION_STATUSES = [
  "registered",
  "intake_pending",
  "intake_submitted",
  "review_completed",
  "resolution_pending",
  "approved",
  "rejected",
  "revision_requested",
  "order_draft_created",
  "under_review",
  "awaiting_director_resolution",
  "resolution_approved",
  "resolution_rejected",
  "completed",
  "withdrawn",
  "cancelled",
  "expired",
] as const;

export type PersonnelApplicationStatus = (typeof PERSONNEL_APPLICATION_STATUSES)[number];

export const PERSONNEL_APPLICATION_STATUS_LABELS: Record<string, string> = {
  registered: "Зарегистрировано",
  intake_pending: "Ожидает анкету",
  intake_submitted: "Анкета получена",
  review_completed: "Проверка завершена",
  resolution_pending: "Ожидает резолюции",
  approved: "Согласовано",
  rejected: "Отказ",
  revision_requested: "На уточнении",
  order_draft_created: "Черновик приказа создан",
  under_review: "На рассмотрении",
  awaiting_director_resolution: "Ожидает резолюции",
  resolution_approved: "Резолюция одобрена",
  resolution_rejected: "Отказ директора",
  completed: "Принят на работу",
  withdrawn: "Отозвано",
  cancelled: "Отменено",
  expired: "Срок анкеты истёк",
};

export const DIRECTOR_RESOLUTION_LABELS: Record<string, string> = {
  pending: "Ожидает",
  approved: "Одобрено",
  rejected: "Отклонено",
  revision_requested: "На уточнении",
};

export const PERSONNEL_APPLICATION_SORT_OPTIONS = [
  { value: "application_received_at_desc", label: "Дата заявления ↓" },
  { value: "application_received_at_asc", label: "Дата заявления ↑" },
  { value: "registered_at_desc", label: "Дата регистрации ↓" },
  { value: "full_name_asc", label: "ФИО А→Я" },
  { value: "status_asc", label: "Статус А→Я" },
] as const;

export function personnelApplicationStatusLabel(status: string | null | undefined): string {
  const key = String(status || "").trim();
  return PERSONNEL_APPLICATION_STATUS_LABELS[key] || key || "—";
}

export function directorResolutionLabel(status: string | null | undefined): string {
  const key = String(status || "").trim();
  if (!key) return "—";
  return DIRECTOR_RESOLUTION_LABELS[key] || key;
}

export function personnelApplicationStatusBadgeClass(status: string): string {
  switch (status) {
    case "registered":
    case "intake_pending":
    case "intake_submitted":
      return "bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-200";
    case "under_review":
    case "awaiting_director_resolution":
    case "resolution_pending":
      return "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200";
    case "resolution_approved":
    case "approved":
    case "order_draft_created":
      return "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200";
    case "review_completed":
      return "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200";
    case "revision_requested":
      return "bg-orange-100 text-orange-900 dark:bg-orange-950 dark:text-orange-200";
    case "completed":
      return "bg-green-100 text-green-900 dark:bg-green-950 dark:text-green-200";
    case "resolution_rejected":
    case "rejected":
    case "withdrawn":
    case "cancelled":
    case "expired":
      return "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300";
    default:
      return "bg-zinc-100 text-zinc-800 dark:bg-zinc-900 dark:text-zinc-200";
  }
}

export function formatPersonnelApplicationDate(value: string | null | undefined): string {
  const trimmed = String(value || "").trim();
  if (!trimmed) return "—";
  const datePart = trimmed.slice(0, 10);
  const [year, month, day] = datePart.split("-");
  if (!year || !month || !day) return trimmed;
  return `${day}.${month}.${year}`;
}

export function formatPersonnelApplicationDateTime(value: string | null | undefined): string {
  const trimmed = String(value || "").trim();
  if (!trimmed) return "—";
  const date = new Date(trimmed);
  if (Number.isNaN(date.getTime())) return formatPersonnelApplicationDate(trimmed);
  return date.toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function isPersonnelApplicationReadOnly(status: string | null | undefined): boolean {
  const key = String(status || "").trim();
  return (
    key === "completed" ||
    key === "withdrawn" ||
    key === "cancelled" ||
    key === "expired" ||
    key === "resolution_rejected" ||
    key === "rejected"
  );
}

export const PERSONNEL_APPLICATION_ARCHIVE_SORT_OPTIONS = [
  { value: "closed_at_desc", label: "Дата закрытия ↓" },
  { value: "application_received_at_desc", label: "Дата заявления ↓" },
  { value: "registered_at_desc", label: "Дата регистрации ↓" },
  { value: "full_name_asc", label: "ФИО А→Я" },
  { value: "status_asc", label: "Статус А→Я" },
] as const;

export function mapPersonnelApplicationBlockReason(code: string | null | undefined): string {
  switch (String(code || "").trim()) {
    case "ACTIVE_EMPLOYEE_BLOCKS_REGISTRATION":
      return "У person есть активный сотрудник — регистрация недоступна.";
    default:
      return code ? String(code) : "—";
  }
}
