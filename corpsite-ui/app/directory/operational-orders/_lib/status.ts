const WORKSPACE_STAGE_LABELS: Record<string, string> = {
  SUBMITTED: "Передан",
  ACCEPTED: "Принят",
  INTAKE_REVIEW: "Проверка приёма",
  CLARIFICATION_REQUIRED: "Требуется уточнение",
  READY_FOR_EDITORIAL: "Готов к редакционной обработке",
  TRANSLATION_REQUIRED: "Требуется перевод",
  TRANSLATION_IN_PROGRESS: "Перевод выполняется",
  CONTENT_CONFIRMATION_REQUIRED: "Требуется подтверждение",
  BILINGUAL_RECONCILIATION: "Согласование RU/KK",
  EDITORIAL_PACKAGE_READY: "Редакционный пакет готов",
  DOCUMENT_PROMOTED: "Официальный проект создан",
};

const DOCUMENT_STATUS_LABELS: Record<string, string> = {
  CREATED: "Создан",
  READY_FOR_SIGNATURE: "Готов к подписи",
  SIGNED: "Подписан",
  REGISTERED: "Зарегистрирован",
  VOIDED: "Аннулирован",
};

const SEVERITY_LABELS: Record<string, string> = {
  INFO: "Информация",
  WARNING: "Предупреждение",
  ERROR: "Ошибка",
};

const DRAFTING_PATH_LABELS: Record<string, string> = {
  SUBMITTED_TEXT: "Переданный текст",
};

const CONFIRMATION_ROLE_LABELS: Record<string, string> = {
  CONTENT_AUTHOR: "Автор содержания",
  TRANSLATOR: "Переводчик",
  DOCUMENT_OPERATOR: "Оператор документа",
};

const TRANSLATION_STATUS_LABELS: Record<string, string> = {
  REQUESTED: "Назначен",
  ACCEPTED: "Принят исполнителем",
  IN_PROGRESS: "Выполняется",
  COMPLETED: "Завершён",
  CANCELLED: "Отменён",
  SUPERSEDED: "Утратил актуальность",
};

const CONFIRMATION_STATUS_LABELS: Record<string, string> = {
  CONFIRMED: "Подтверждено",
  REVOKED: "Отозвано",
  SUPERSEDED: "Утратило актуальность",
};

const RECONCILIATION_STATUS_LABELS: Record<string, string> = {
  PENDING: "Ожидает согласования",
  RECONCILED: "Согласовано",
  INVALIDATED: "Недействительно",
  SUPERSEDED: "Утратило актуальность",
};

const ACTIVE_TRANSLATION_STATUSES = new Set(["REQUESTED", "ACCEPTED", "IN_PROGRESS"]);
const HISTORICAL_TRANSLATION_STATUSES = new Set(["COMPLETED", "CANCELLED", "SUPERSEDED"]);

const CURRENT_CONFIRMATION_STATUSES = new Set(["CONFIRMED"]);
const HISTORICAL_CONFIRMATION_STATUSES = new Set(["REVOKED", "SUPERSEDED"]);

const CURRENT_RECONCILIATION_STATUSES = new Set(["PENDING", "RECONCILED"]);
const HISTORICAL_RECONCILIATION_STATUSES = new Set(["INVALIDATED", "SUPERSEDED"]);

export function workspaceStageLabel(stage: string): string {
  return WORKSPACE_STAGE_LABELS[stage] ?? stage;
}

export function documentStatusLabel(status: string): string {
  return DOCUMENT_STATUS_LABELS[status] ?? status;
}

export function validationSeverityLabel(severity: string): string {
  return SEVERITY_LABELS[severity.toUpperCase()] ?? severity;
}

export function draftingPathLabel(path: string): string {
  return DRAFTING_PATH_LABELS[path] ?? path;
}

export function confirmationRoleLabel(role: string): string {
  return CONFIRMATION_ROLE_LABELS[role] ?? role;
}

export function translationStatusLabel(status: string): string {
  return TRANSLATION_STATUS_LABELS[status] ?? status;
}

export function confirmationStatusLabel(status: string): string {
  return CONFIRMATION_STATUS_LABELS[status] ?? status;
}

export function reconciliationStatusLabel(status: string): string {
  return RECONCILIATION_STATUS_LABELS[status] ?? status;
}

export function isActiveTranslationStatus(status: string): boolean {
  return ACTIVE_TRANSLATION_STATUSES.has(status);
}

export function isHistoricalTranslationStatus(status: string): boolean {
  return HISTORICAL_TRANSLATION_STATUSES.has(status);
}

export function isCurrentConfirmationStatus(status: string): boolean {
  return CURRENT_CONFIRMATION_STATUSES.has(status);
}

export function isHistoricalConfirmationStatus(status: string): boolean {
  return HISTORICAL_CONFIRMATION_STATUSES.has(status);
}

export function isCurrentReconciliationStatus(status: string): boolean {
  return CURRENT_RECONCILIATION_STATUSES.has(status);
}

export function isHistoricalReconciliationStatus(status: string): boolean {
  return HISTORICAL_RECONCILIATION_STATUSES.has(status);
}

export function translationStatusBadgeClass(status: string): string {
  if (status === "COMPLETED") return "border-emerald-200 bg-emerald-50 text-emerald-800";
  if (status === "IN_PROGRESS" || status === "ACCEPTED") return "border-blue-200 bg-blue-50 text-blue-800";
  if (status === "CANCELLED" || status === "SUPERSEDED") return "border-zinc-200 bg-zinc-50 text-zinc-600";
  return "border-amber-200 bg-amber-50 text-amber-900";
}

export function confirmationStatusBadgeClass(status: string): string {
  if (status === "CONFIRMED") return "border-emerald-200 bg-emerald-50 text-emerald-800";
  if (status === "REVOKED") return "border-red-200 bg-red-50 text-red-800";
  return "border-zinc-200 bg-zinc-50 text-zinc-600";
}

export function reconciliationStatusBadgeClass(status: string): string {
  if (status === "RECONCILED") return "border-emerald-200 bg-emerald-50 text-emerald-800";
  if (status === "PENDING") return "border-amber-200 bg-amber-50 text-amber-900";
  return "border-zinc-200 bg-zinc-50 text-zinc-600";
}

export function workspaceStageBadgeClass(stage: string): string {
  if (stage === "DOCUMENT_PROMOTED") {
    return "border-purple-200 bg-purple-50 text-purple-800 dark:border-purple-900 dark:bg-purple-950/40 dark:text-purple-200";
  }
  if (stage === "EDITORIAL_PACKAGE_READY") {
    return "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-200";
  }
  if (stage === "CLARIFICATION_REQUIRED") {
    return "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100";
  }
  if (stage.includes("TRANSLATION") || stage.includes("RECONCILIATION") || stage.includes("CONFIRMATION")) {
    return "border-blue-200 bg-blue-50 text-blue-800 dark:border-blue-900 dark:bg-blue-950/40 dark:text-blue-200";
  }
  return "border-zinc-200 bg-zinc-50 text-zinc-700 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200";
}

export function documentStatusBadgeClass(status: string): string {
  if (status === "READY_FOR_SIGNATURE") {
    return "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-200";
  }
  if (status === "CREATED") {
    return "border-blue-200 bg-blue-50 text-blue-800 dark:border-blue-900 dark:bg-blue-950/40 dark:text-blue-200";
  }
  return "border-zinc-200 bg-zinc-50 text-zinc-700 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200";
}

export function isWorkspaceFrozen(stage: string): boolean {
  return stage === "DOCUMENT_PROMOTED";
}

export const WORKSPACE_STAGE_FILTER_OPTIONS = Object.entries(WORKSPACE_STAGE_LABELS).map(
  ([value, label]) => ({ value, label }),
);

export const DOCUMENT_STATUS_FILTER_OPTIONS = [
  { value: "CREATED", label: documentStatusLabel("CREATED") },
  { value: "READY_FOR_SIGNATURE", label: documentStatusLabel("READY_FOR_SIGNATURE") },
];
