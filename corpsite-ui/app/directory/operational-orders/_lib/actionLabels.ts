const AUDIT_ACTION_LABELS: Record<string, string> = {
  SUBMISSION_CREATED: "Создана заявка",
  WORKSPACE_ACCEPTED: "Рабочее пространство принято",
  BLOCK_ADDED: "Добавлен блок текста",
  EFFECTIVE_TEXT_CHANGED: "Изменён рабочий текст",
  PROVENANCE_ADDED: "Запись происхождения текста",
  VALIDATION_EXECUTED: "Выполнена проверка",
  CLARIFICATION_OPENED: "Открыто уточнение",
  CLARIFICATION_RESOLVED: "Уточнение закрыто",
  READY_FOR_EDITORIAL: "Передано в редакционную обработку",
  TRANSLATION_REQUESTED: "Запрошен перевод",
  TRANSLATOR_ASSIGNED: "Назначен переводчик",
  ASSIGNMENT_ACCEPTED: "Перевод принят исполнителем",
  TRANSLATION_STARTED: "Перевод начат",
  TRANSLATION_COMPLETED: "Перевод завершён",
  CONFIRMATION_CREATED: "Создано подтверждение",
  CONFIRMATION_REVOKED: "Подтверждение отозвано",
  CONFIRMATION_SUPERSEDED: "Подтверждение утратило актуальность",
  RECONCILIATION_CREATED: "Создано согласование RU/KK",
  RECONCILIATION_INVALIDATED: "Согласование недействительно",
  WORKSPACE_STAGE_CHANGED: "Изменена стадия",
  EDITORIAL_PACKAGE_READY: "Редакционный пакет готов",
  EDITORIAL_PACKAGE_VALIDATION_FAILED: "Проверка редакционного пакета не пройдена",
  WORKSPACE_FROZEN: "Рабочее пространство заморожено",
  PROMOTION_REPLAY: "Повтор promotion (replay)",
  REVISION_ADVISORY_RETURNED: "Рекомендована новая редакция",
  PROMOTION_STARTED: "Promotion начат",
  PROMOTION_COMPLETED: "Promotion завершён",
  PROMOTION_FAILED: "Promotion не выполнен",
  DOCUMENT_CREATED: "Создан официальный документ",
  VERSION_CREATED: "Создана версия документа",
  LOCALIZATION_SNAPSHOTTED: "Снимок локализаций",
  SIGNING_AUTHORITY_ASSIGNED: "Назначен подписант",
  SIGNING_AUTHORITY_SUPERSEDED: "Подписант заменён",
  SIGNATURE_READINESS_VALIDATED: "Проверена готовность к подписи",
  SIGNATURE_READINESS_FAILED: "Проверка готовности не пройдена",
  DOCUMENT_READY_FOR_SIGNATURE: "Документ передан на подпись",
  READY_FOR_SIGNATURE_REPLAY: "Повтор передачи на подпись (replay)",
  DOCUMENT_RETURNED_TO_CREATED: "Документ возвращён из очереди подписи",
};

const PROVENANCE_ACTION_LABELS: Record<string, string> = {
  SUBMISSION: "Первичная подача",
  ACCEPTANCE: "Принятие",
  BLOCK_ADD: "Добавление блока",
  EFFECTIVE_EDIT: "Редактирование текста",
  PROMOTED_FROM_WORKSPACE: "Promotion из workspace",
  PROMOTION_REPLAY: "Promotion replay",
  SNAPSHOT_CREATED: "Создан снимок",
  DOCUMENT_VERSION_CREATED: "Создана версия документа",
  WORKSPACE_DRIFT_DETECTED: "Обнаружено расхождение workspace",
};

export function auditActionLabel(action: string): string {
  return AUDIT_ACTION_LABELS[action] ?? action;
}

export function provenanceActionLabel(action: string): string {
  return PROVENANCE_ACTION_LABELS[action] ?? action;
}
