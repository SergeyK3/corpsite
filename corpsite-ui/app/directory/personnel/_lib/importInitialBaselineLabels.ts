/** UI labels for first baseline formation (/import/review?mode=initial). */

export const INITIAL_BASELINE_UI = {
  pageTitle: "Первичное формирование эталона",
  pageLead:
    "Проверьте результаты конвертации контрольного списка и подготовьте данные для создания первого месячного эталона.",
  blockedJulyNotice:
    "Сначала сформируйте эталон за июнь 2026. После этого можно будет подготовить эталон за июль.",
  importPickerLabel: "Импорт контрольного списка",
  importPickerHint: "Выберите импорт со статусом «Проверка завершена» за выбранный период.",
  noImportsHint:
    "Нет импортов со статусом «Проверка завершена» за выбранный период. Завершите проверку на странице normalized-записей.",
  summaryTitle: "Сводка по неправильным данным",
  summaryTotalRows: "Всего строк",
  summaryRowsWithoutErrors: "Строк без ошибок",
  summaryRowsWithErrors: "Строк с ошибками",
  summaryTotalIssues: "Общее количество ошибок",
  summaryEmployeesWithErrors: "Сотрудников с ошибками",
  summaryIssuesByCodeTitle: "Ошибки по типу",
  peopleTitle: "Люди из контрольного файла",
  fixDataAction: "Проверить данные",
  sourceValueLabel: "Контрольный файл",
  normalizedValueLabel: "Нормализованное значение",
  manualValueLabel: "Исправленное значение",
  personMatchLabel: "Сопоставление с Person",
  readinessLabel: "Готовность к эталону",
  issuesLabel: "Проблемы",
  createBaselineAction: "Создать эталон июня 2026",
  createBaselineDisabledNote: "Сначала необходимо завершить проверку данных",
  createBaselineFoundationNote:
    "Команда первичного создания MRD будет выполняться на backend после подключения сервиса create_initial_mrd_from_review.",
} as const;

export const PERSON_MATCH_LABELS: Record<string, string> = {
  matched: "Сопоставлен с Person",
  unmatched: "Person не найден — требуется проверка",
  unknown: "Сопоставление не выполнено",
};

export const READINESS_STATUS_LABELS: Record<string, string> = {
  ready: "Готов к включению",
  needs_review: "Требует проверки",
  blocked: "Заблокирован",
};

export const IMPORT_ROW_ISSUE_LABELS: Record<string, string> = {
  missing_full_name: "Не указано ФИО",
  missing_iin: "Не указан ИИН",
  invalid_iin: "Некорректный ИИН",
  invalid_iin_checksum: "Некорректная контрольная сумма ИИН",
  duplicate_iin: "Дублирующийся ИИН в файле",
  missing_department: "Не указано отделение",
  missing_position: "Не указана должность",
  org_unit_unresolved: "Отделение не сопоставлено со справочником",
};

export function importRowIssueLabel(code: string): string {
  return IMPORT_ROW_ISSUE_LABELS[code] ?? code.replace(/_/g, " ");
}
