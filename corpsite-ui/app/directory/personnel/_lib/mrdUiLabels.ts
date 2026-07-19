/** Единая русская терминология UI эталонов. В коде/API/БД сохраняются технические имена. */

export const MRD_UI = {
  productTitle: "Ежемесячные эталоны кадровых данных",
  createWizardTitle: "Создание эталона следующего периода",
  createWizardLead:
    "Будет создан рабочий эталон следующего календарного месяца на основе действующего эталона выбранного периода.",
  lockedSourceLabel: "Исходный период",
  lockedTargetLabel: "Следующий период",
  createNextPeriodAction: "Создать следующий период",
  createBaselineAction: "Создать эталон",
  workWithBaselineAction: "Работать с эталоном",
  formInitialBaselineAction: "Сформировать эталон",
  journalLink: "К журналу эталонов",
  insufficientPermissions: "Недостаточно прав для работы с ежемесячными эталонами кадровых данных.",

  targetPeriodLabel: "Следующий отчётный период",
  notesLabel: "Примечание",
  notesOptional: "необязательно",

  submitCreate: "Создать следующий период",
  submitting: "Выполнение…",

  journalLead:
    "Отображаются только предыдущий, текущий и следующий календарные месяцы. Для каждого периода — один эталон.",
  journalNotCreatedStatus: "Не создан",
  journalPeriodColumn: "Период",
  journalStatusColumn: "Статус",
  journalEntriesColumn: "Записей",
  journalActionColumn: "Действия",
  journalMrdEmpty: "Эталоны ещё не созданы. После первого эталона здесь появится журнал периодов.",
  legacyArchiveTitle: "Архивные публикации из импорта",
  legacyArchiveLead:
    "Исторические публикации до перехода на ежемесячные эталоны. Только просмотр и архивные операции.",
  legacyArchiveEmpty: "Архивные публикации не найдены.",
  journalInsufficientPermissions: "Недостаточно прав для просмотра журнала эталонов.",
  archiveTableId: "Публикация",
  showDeleted: "Показывать удалённые",

  reviewLead:
    "После проверки нормализованных записей и устранения ошибок парсинга завершите проверку, чтобы перейти к работе с эталонами.",
  reviewReadyPrefix: "Импорт проверен. Далее можно перейти к эталону в ",
  reviewReadyLink: "журнале эталонов",
  reviewReadySuffix: ".",
  reviewDialogLead:
    "Перед завершением система проверит отсутствие блокирующих условий. После завершения импорт будет готов к сопоставлению с эталоном.",
  createEtalonLink: "Перейти к эталонам",

  selectSourceError: "Не выбран исходный эталон.",
  selectTargetError: "Выберите допустимый период создания.",
  successCopiedEntries: (count: number) => `Скопировано записей: ${count}.`,
  successCreatedPeriod: (periodLabel: string) => `Создан эталон за ${periodLabel}.`,
  creationWindowHint:
    "Доступны только предыдущий, текущий и следующий календарные месяцы относительно сегодняшней даты.",

  detectedDifferencesTitle: "Обнаруженные изменения",
  detectedDifferencesLead:
    "Перед созданием следующего периода можно просмотреть журнал обнаруженных изменений по исходному периоду.",
  detectedDifferencesLink: "Открыть обнаруженные изменения",

  etalonGroupLabel: "Группа отделений",
  etalonDepartmentLabel: "Отделение",
  etalonSearchLabel: "Поиск сотрудника",
  etalonSearchPlaceholder: "ФИО…",
  etalonChangedOnly: "Только с изменениями",
  etalonAllEmployees: "Все сотрудники",
  etalonSelectDepartmentHint: "Выберите группу и отделение, чтобы увидеть сотрудников с обнаруженными изменениями.",
  etalonSummaryTotal: "Всего сотрудников",
  etalonSummaryWithoutChanges: "Без изменений",
  etalonSummaryWithChanges: "С изменениями",
  etalonSummaryAwaiting: "Ожидают решения",
  etalonSummaryConfirmed: "Подтверждено",
  etalonSummaryRejected: "Отклонено",
  etalonEmployeesEmpty: "По выбранным фильтрам сотрудники не найдены.",
  etalonDifferenceWas: "Было",
  etalonDifferenceDetected: "Обнаружено",
  etalonDifferenceSource: "Источник",
  etalonDifferenceDecision: "Статус решения",
  etalonConfirmAction: "Подтвердить",
  etalonModifyConfirmAction: "Изменить и подтвердить",
  etalonRejectAction: "Отклонить",

  secondaryLinksTitle: "Дополнительно",
  secondaryImportReviewLink: "Проверка нормализованных записей импорта",
  secondaryConfirmedJournalLink: "Журнал подтверждённых изменений",
  secondaryMigrationLink: "Миграция в кадровое досье",
  secondaryTechnicalInfoLink: "Технические сведения об эталоне",
} as const;
