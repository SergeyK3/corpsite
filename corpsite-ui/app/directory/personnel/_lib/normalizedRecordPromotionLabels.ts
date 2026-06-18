// ADR-039 Phase 3F.2 — promotion blocker and skip reason labels for Review UI.

/** Failure blocker codes emitted by hr_import_promotion_service. */
export const PROMOTION_BLOCKER_CODES = [
  "NOT_APPROVED",
  "EMPLOYEE_REQUIRED",
  "DOCUMENT_TYPE_UNRESOLVED",
  "MEDICAL_SPECIALTY_UNRESOLVED",
  "VALIDATION_MISSING_VALID_UNTIL",
  "VALIDATION_MISSING_HOURS_OR_ISSUED_AT",
] as const;

export type PromotionBlockerCode = (typeof PROMOTION_BLOCKER_CODES)[number];

export const PROMOTION_BLOCKER_LABELS: Record<PromotionBlockerCode, string> = {
  NOT_APPROVED: "Запись не утверждена",
  EMPLOYEE_REQUIRED: "Сотрудник не привязан",
  DOCUMENT_TYPE_UNRESOLVED: "Тип документа не определён",
  MEDICAL_SPECIALTY_UNRESOLVED: "Медицинская специальность не определена",
  VALIDATION_MISSING_VALID_UNTIL: "Не указан срок действия",
  VALIDATION_MISSING_HOURS_OR_ISSUED_AT: "Не указаны часы или дата выдачи",
};

/** Panel groups shown on the promotion blockers summary. */
export const PROMOTION_BLOCKER_PANEL_GROUPS = [
  {
    key: "MEDICAL_SPECIALTY_UNRESOLVED",
    label: "Медицинская специальность не определена",
    codes: ["MEDICAL_SPECIALTY_UNRESOLVED"],
  },
  {
    key: "DOCUMENT_TYPE_UNRESOLVED",
    label: "Тип документа не определён",
    codes: ["DOCUMENT_TYPE_UNRESOLVED"],
  },
  {
    key: "EMPLOYEE_REQUIRED",
    label: "Сотрудник не привязан",
    codes: ["EMPLOYEE_REQUIRED"],
  },
  {
    key: "VALIDATION",
    label: "Ошибки валидации",
    codes: ["VALIDATION_MISSING_VALID_UNTIL", "VALIDATION_MISSING_HOURS_OR_ISSUED_AT"],
  },
] as const;

export const PROMOTION_SKIP_REASON_LABELS: Record<string, string> = {
  ALREADY_PROMOTED: "Уже промотировано",
  DUPLICATE_ACTIVE_DOCUMENT: "Дубликат активного документа",
};

export function getPromotionBlockerLabel(code: string): string {
  return PROMOTION_BLOCKER_LABELS[code as PromotionBlockerCode] ?? code;
}

export function sumBlockersByCodes(
  summary: Record<string, number>,
  codes: readonly string[],
): number {
  return codes.reduce((acc, code) => acc + (summary[code] ?? 0), 0);
}
