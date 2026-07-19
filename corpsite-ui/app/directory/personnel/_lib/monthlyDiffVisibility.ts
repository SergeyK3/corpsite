/** Пояснение метрики review_visibility.visible_records (ADR-040 review-by-exception). */
export const VISIBLE_RECORDS_LABEL = "Требуют внимания в diff";

export const VISIBLE_RECORDS_HELP =
  "Сумма записей со статусами NEW, CHANGED, CONFLICT и REMOVED без решения. " +
  "Не совпадает с размером формируемого эталона: восстановленные и подтверждённые removals из этого счётчика исключаются.";

export function formatVisibleRecordsFormula(parts: {
  newCount: number;
  changedCount: number;
  conflictCount: number;
  pendingRemovals: number;
}): string {
  return `${parts.newCount} NEW + ${parts.changedCount} CHANGED + ${parts.conflictCount} CONFLICT + ${parts.pendingRemovals} REMOVED (без решения)`;
}
