import { personnelApplicationStatusLabel } from "./personnelApplicationLabels";

export const PERSONNEL_LK_RECORD_KIND_LABELS: Record<string, string> = {
  employee: "Сотрудник",
  applicant: "Претендент",
};

export const PERSONNEL_LK_TYPE_FILTER_OPTIONS = [
  { value: "", label: "Все типы" },
  { value: "employee", label: "Сотрудник" },
  { value: "applicant", label: "Претендент" },
] as const;

export const PERSONNEL_LK_EMPLOYEE_STATUS_FILTER_OPTIONS = [
  { value: "active", label: "Работает" },
  { value: "inactive", label: "Не работает" },
  { value: "all", label: "Все сотрудники" },
] as const;

export const PERSONNEL_LK_APPLICATION_STATUS_FILTER_OPTIONS = [
  { value: "", label: "Любой статус заявки" },
  { value: "registered", label: "Зарегистрировано" },
  { value: "intake_pending", label: "Ожидает анкету" },
  { value: "intake_submitted", label: "Личная карточка заполнена" },
  { value: "review_completed", label: "Проверка завершена" },
  { value: "order_draft_created", label: "Черновик приказа создан" },
  { value: "completed", label: "Принят на работу" },
] as const;

export function personnelLkRecordKindLabel(recordKind: string | null | undefined): string {
  const key = String(recordKind ?? "").trim();
  return PERSONNEL_LK_RECORD_KIND_LABELS[key] || key || "—";
}

export function personnelLkStatusLabel(item: {
  record_kind: string;
  status: string;
  application_status?: string | null;
}): string {
  if (item.record_kind === "applicant") {
    return personnelApplicationStatusLabel(item.application_status || item.status);
  }
  if (item.status === "active") return "Работает";
  if (item.status === "inactive") return "Не работает";
  return item.status || "—";
}

export function formatPersonnelLkRate(rate: number | string | null | undefined): string {
  if (rate == null || rate === "") return "—";
  const numeric = Number(String(rate).replace(",", "."));
  if (!Number.isFinite(numeric)) return String(rate);
  return numeric.toLocaleString("ru-RU", { maximumFractionDigits: 2 });
}
