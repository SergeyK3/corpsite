// FILE: corpsite-ui/app/admin/system/_lib/userLinkageOperationsLabels.ts

export const OPERATION_OPTIONS = [
  "",
  "USER_LINKAGE_EXECUTE",
  "USER_LINKAGE_EXECUTE_PREVIEW",
  "USER_LINKAGE_MANUAL_LINK",
  "USER_LINKAGE_MANUAL_UNLINK",
  "USER_LINKAGE_ROLLBACK_ITEM",
  "USER_LINKAGE_REPAIR_PREVIEW",
  "USER_LINKAGE_RERUN_EXECUTE",
] as const;

export const RUN_STATUS_OPTIONS = ["", "running", "completed", "failed"] as const;

export const ITEM_ACTION_OPTIONS = [
  "",
  "LINK",
  "MANUAL_LINK",
  "MANUAL_UNLINK",
  "ROLLBACK_LINK",
  "REPAIR_PREVIEW",
  "RERUN_EXECUTE",
  "NOOP_ALREADY_LINKED",
  "SKIP_NOT_APPROVED",
  "SKIP_PREVIEW_DRIFT",
  "SKIP_CLASSIFICATION_REGRESSION",
  "SKIP_EXCLUDED",
  "FAIL_ALREADY_LINKED_DIFFERENT",
  "FAIL_EMPLOYEE_CONFLICT",
] as const;

export const ITEM_STATUS_OPTIONS = [
  "",
  "PLANNED",
  "APPLIED",
  "SKIPPED",
  "FAILED",
  "NOOP_ALREADY_LINKED",
  "NOOP_ALREADY_UNLINKED",
  "NOOP_ALREADY_ROLLED_BACK",
] as const;

export function filterAllLabel(): string {
  return "Все";
}

export function yesNoLabel(value: boolean): string {
  return value ? "Да" : "Нет";
}

export function operationLabel(operation: string): string {
  const map: Record<string, string> = {
    USER_LINKAGE_EXECUTE: "Выполнение",
    USER_LINKAGE_EXECUTE_PREVIEW: "Предпросмотр выполнения",
    USER_LINKAGE_MANUAL_LINK: "Ручная привязка",
    USER_LINKAGE_MANUAL_UNLINK: "Ручная отвязка",
    USER_LINKAGE_ROLLBACK_ITEM: "Откат",
    USER_LINKAGE_REPAIR_PREVIEW: "Диагностика привязки",
    USER_LINKAGE_RERUN_EXECUTE: "Повторное выполнение",
  };
  return map[operation] ?? operation;
}

export function runStatusLabel(status: string): string {
  const map: Record<string, string> = {
    running: "Выполняется",
    completed: "Завершён",
    failed: "Ошибка",
  };
  return map[status] ?? status;
}

export function itemStatusLabel(status: string): string {
  const map: Record<string, string> = {
    PLANNED: "Запланировано",
    APPLIED: "Применено",
    SKIPPED: "Пропущено",
    FAILED: "Ошибка",
    NOOP_ALREADY_LINKED: "Уже привязан",
    NOOP_ALREADY_UNLINKED: "Уже отвязан",
    NOOP_ALREADY_ROLLED_BACK: "Уже откатан",
  };
  return map[status] ?? status;
}

export function itemActionLabel(action: string): string {
  const map: Record<string, string> = {
    LINK: "Привязка",
    MANUAL_LINK: "Ручная привязка",
    MANUAL_UNLINK: "Ручная отвязка",
    ROLLBACK_LINK: "Откат привязки",
    REPAIR_PREVIEW: "Диагностика",
    RERUN_EXECUTE: "Повторное выполнение",
    NOOP_ALREADY_LINKED: "Уже привязан",
    SKIP_NOT_APPROVED: "Пропуск: не одобрено",
    SKIP_PREVIEW_DRIFT: "Пропуск: расхождение предпросмотра",
    SKIP_CLASSIFICATION_REGRESSION: "Пропуск: регресс классификации",
    SKIP_EXCLUDED: "Пропуск: исключён",
    FAIL_ALREADY_LINKED_DIFFERENT: "Ошибка: привязан к другому",
    FAIL_EMPLOYEE_CONFLICT: "Ошибка: конфликт сотрудника",
  };
  return map[action] ?? action;
}

export function diagnosisLabel(code: string): string {
  const map: Record<string, string> = {
    LINK_OK: "Привязка в порядке",
    USER_UNLINKED_EMPLOYEE_MATCH_FOUND: "Пользователь отвязан, найден сотрудник",
    USER_LINKED_TO_DIFFERENT_EMPLOYEE: "Пользователь привязан к другому сотруднику",
    EMPLOYEE_LINKED_TO_DIFFERENT_USER: "Сотрудник привязан к другому пользователю",
    NO_CANDIDATE_FOUND: "Кандидат не найден",
    USER_NOT_FOUND: "Пользователь не найден",
    EMPLOYEE_NOT_FOUND: "Сотрудник не найден",
    SERVICE_ACCOUNT_EXCLUDED: "Служебная учётная запись исключена",
    INACTIVE_EMPLOYEE_TARGET: "Целевой сотрудник неактивен",
    REVIEW_REQUIRED: "Требуется проверка",
    CONFLICT_REQUIRES_MANUAL_DECISION: "Конфликт: требуется ручное решение",
    MANUAL_DECISION: "Требуется ручное решение",
  };
  return map[code] ?? code;
}

export function recommendedActionLabel(action: string): string {
  const map: Record<string, string> = {
    NO_ACTION: "Действий не требуется",
    RE_EXECUTE: "Повторить выполнение",
    RE_REVIEW: "Повторить проверку",
    MANUAL_DECISION: "Ручное решение",
  };
  return map[action] ?? action;
}

export function runStatusClass(status: string): string {
  switch (status) {
    case "completed":
      return "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200";
    case "failed":
      return "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-200";
    case "running":
      return "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200";
    default:
      return "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-200";
  }
}

export function itemStatusClass(status: string): string {
  switch (status) {
    case "APPLIED":
      return "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200";
    case "FAILED":
      return "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-200";
    case "SKIPPED":
      return "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200";
    case "PLANNED":
      return "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200";
    default:
      return "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-200";
  }
}

export type DiagnosisTone = "green" | "yellow" | "orange" | "red" | "muted";

export function diagnosisTone(code: string): DiagnosisTone {
  if (code === "LINK_OK") return "green";
  if (code === "REVIEW_REQUIRED") return "yellow";
  if (code === "MANUAL_DECISION") return "orange";
  if (code === "CONFLICT_REQUIRES_MANUAL_DECISION") return "red";
  return "muted";
}

export function diagnosisClass(tone: DiagnosisTone): string {
  const base = "rounded-lg border px-3 py-2";
  switch (tone) {
    case "green":
      return `${base} border-emerald-200 bg-emerald-50 dark:border-emerald-900 dark:bg-emerald-950/40`;
    case "yellow":
      return `${base} border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/40`;
    case "orange":
      return `${base} border-orange-200 bg-orange-50 dark:border-orange-900 dark:bg-orange-950/40`;
    case "red":
      return `${base} border-rose-200 bg-rose-50 dark:border-rose-900 dark:bg-rose-950/40`;
    default:
      return `${base} border-zinc-200 bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900/40`;
  }
}

export function summaryCardClass(kind: "info" | "warn" | "success" | "danger" | "muted"): string {
  const base = "rounded-lg border px-3 py-2";
  switch (kind) {
    case "info":
      return `${base} border-blue-200 bg-blue-50 dark:border-blue-900 dark:bg-blue-950/40`;
    case "warn":
      return `${base} border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/40`;
    case "success":
      return `${base} border-emerald-200 bg-emerald-50 dark:border-emerald-900 dark:bg-emerald-950/40`;
    case "danger":
      return `${base} border-rose-200 bg-rose-50 dark:border-rose-900 dark:bg-rose-950/40`;
    default:
      return `${base} border-zinc-200 bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900/40`;
  }
}

export function formatAuditSummary(summary: {
  user_employee_linked: number;
  user_employee_unlinked: number;
  user_employee_link_rolled_back: number;
}): string {
  const parts: string[] = [];
  if (summary.user_employee_linked) parts.push(`привязано ${summary.user_employee_linked}`);
  if (summary.user_employee_unlinked) parts.push(`отвязано ${summary.user_employee_unlinked}`);
  if (summary.user_employee_link_rolled_back) parts.push(`откатов ${summary.user_employee_link_rolled_back}`);
  return parts.length ? parts.join(", ") : "—";
}

export function operationFilterLabel(value: string): string {
  return value ? operationLabel(value) : filterAllLabel();
}

export function runStatusFilterLabel(value: string): string {
  return value ? runStatusLabel(value) : filterAllLabel();
}

export function itemActionFilterLabel(value: string): string {
  return value ? itemActionLabel(value) : filterAllLabel();
}

export function itemStatusFilterLabel(value: string): string {
  return value ? itemStatusLabel(value) : filterAllLabel();
}
