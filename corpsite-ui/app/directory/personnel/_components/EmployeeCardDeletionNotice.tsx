"use client";

const DELETION_NOTICE_TEXT =
  "Удаление сотрудника из справочника персонала выполняется в модуле кадрового контура. " +
  "Это действие доступно только сотрудникам отдела кадров с соответствующими полномочиями.";

export default function EmployeeCardDeletionNotice() {
  return (
    <aside
      aria-label="Сведения об удалении сотрудника"
      data-testid="employee-card-deletion-notice"
      className="rounded-xl border border-zinc-200 bg-zinc-50/80 px-4 py-3 text-sm leading-relaxed text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900/40 dark:text-zinc-400"
    >
      {DELETION_NOTICE_TEXT}
    </aside>
  );
}
