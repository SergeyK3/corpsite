/** UI labels for /directory/personnel/import/review — HR control-list discrepancy workspace. */

export const IMPORT_HR_REVIEW_UI = {
  pageTitle: "Проверка несоответствий контрольного списка",
  pageLead:
    "Сравнение контрольного списка с выбранным месячным эталоном. Исправляйте данные по каждому сотруднику перед переносом в кадровое досье.",
  periodLabel: "Отчётный период",
  selectDepartmentHint: "Выберите группу и отделение, чтобы увидеть сотрудников с несоответствиями.",
  employeesEmpty: "По выбранным фильтрам сотрудники не найдены.",
  employeesSection: "Сотрудники",
  fixDataAction: "Исправить данные",
  baselineLabel: "Эталон",
  controlListLabel: "Контрольный список",
  correctedValueLabel: "Исправленное значение",
  sourceLabel: "Источник",
  fieldStatusLabel: "Статус поля",
  saveAction: "Сохранить исправления",
  saveDisabledNote: "Сохранение будет подключено следующим этапом",
  summaryTotalChecked: "Всего людей проверено",
  summaryWithDiscrepancies: "Людей с несоответствиями",
  summaryTotalDiscrepancies: "Всего несоответствий",
  summaryFixed: "Исправлено",
  summaryRemaining: "Осталось исправить",
  groupFilterLabel: "Группа отделений",
  departmentFilterLabel: "Отделение",
  searchLabel: "Поиск по ФИО",
  searchPlaceholder: "ФИО…",
  statusFilterLabel: "Статус",
  discrepanciesColumn: "Несоответствия",
  problemsColumn: "Проблемы",
  positionColumn: "Должность",
  departmentColumn: "Отделение",
  noMrdHint: "Для выбранного периода эталон не найден. Создайте эталон в журнале или укажите mrd_id в адресе страницы.",
} as const;

export type ImportHrReviewStatusFilter = "needs_fix" | "partial" | "fixed" | "all";

export const IMPORT_HR_REVIEW_STATUS_FILTER_OPTIONS: Array<{
  value: ImportHrReviewStatusFilter;
  label: string;
}> = [
  { value: "needs_fix", label: "Требуют исправления" },
  { value: "partial", label: "Частично исправлены" },
  { value: "fixed", label: "Исправлены" },
  { value: "all", label: "Все" },
];

export const IMPORT_HR_REVIEW_EMPLOYEE_STATUS_LABELS: Record<string, string> = {
  PENDING: "Требуют исправления",
  PARTIAL: "Частично исправлено",
  REVIEWED: "Исправлено",
  NO_CHANGES: "Без несоответствий",
};

export function importHrReviewEmployeeStatusLabel(status: string): string {
  return IMPORT_HR_REVIEW_EMPLOYEE_STATUS_LABELS[status] ?? status;
}

export function importHrReviewEmployeeStatusClassName(status: string): string {
  if (status === "REVIEWED") {
    return "border-green-200 bg-green-100 text-green-900 dark:border-green-800 dark:bg-green-950/50 dark:text-green-200";
  }
  if (status === "PARTIAL") {
    return "border-amber-200 bg-amber-100 text-amber-900 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-200";
  }
  if (status === "PENDING") {
    return "border-red-200 bg-red-100 text-red-900 dark:border-red-800 dark:bg-red-950/50 dark:text-red-200";
  }
  return "border-zinc-200 bg-zinc-100 text-zinc-700 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300";
}
