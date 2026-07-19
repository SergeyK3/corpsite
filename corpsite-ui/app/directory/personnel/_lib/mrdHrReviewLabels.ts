/** HR review status labels for the baseline working screen. */
export const HR_REVIEW_STATUS_LABELS: Record<string, string> = {
  PENDING: "Ожидает решения",
  PARTIAL: "Частично рассмотрено",
  REVIEWED: "Рассмотрено",
  NO_CHANGES: "Нет изменений",
};

export const HR_DECISION_STATUS_LABELS: Record<string, string> = {
  AWAITING: "Ожидает решения",
  CONFIRMED: "Подтверждено",
  REJECTED: "Отклонено",
};

export function hrReviewStatusLabel(status: string): string {
  return HR_REVIEW_STATUS_LABELS[status] ?? status;
}

export function hrDecisionStatusLabel(status: string): string {
  return HR_DECISION_STATUS_LABELS[status] ?? status;
}
