"use client";

import type { TestEmployeeCleanupResult } from "../_lib/personnelLkApi.client";

export default function TestEmployeeCleanupResultDialog({ result, onClose }: {
  result: TestEmployeeCleanupResult;
  onClose: () => void;
}) {
  const deletedRecords = Object.values(result.deleted_counts).reduce((sum, count) => sum + count, 0);
  const retainedRecords = Object.values(result.retained_counts ?? {}).reduce((sum, count) => sum + count, 0);
  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60 p-4">
      <section role="dialog" aria-modal="true" aria-label="Результат удаления тестового сотрудника" className="w-full max-w-md rounded-xl bg-white p-5 shadow-xl dark:bg-zinc-900">
        <h2 className="text-lg font-semibold">Тестовый сотрудник и связанные с ним данные удалены</h2>
        <p className="mt-3 font-medium">{result.full_name}</p>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">Сотрудник ID {result.employee_id}</p>
        <dl className="mt-4 grid grid-cols-[1fr_auto] gap-x-3 gap-y-2 text-sm">
          <dt>Удалено записей</dt><dd className="text-right font-medium">{deletedRecords}</dd>
          <dt>Удалено файлов</dt><dd className="text-right font-medium">{result.file_cleanup.deleted_files ?? 0}</dd>
          <dt>Сохранено исторических записей</dt><dd className="text-right font-medium">{retainedRecords}</dd>
          <dt>Очистка файлов</dt><dd className="text-right font-medium">{result.file_cleanup.pending ? `Ожидают повторной очистки: ${result.file_cleanup.pending}` : "Завершена"}</dd>
        </dl>
        <div className="mt-5 flex justify-end"><button type="button" onClick={onClose} className="rounded-md border px-3 py-2 text-sm">Закрыть</button></div>
      </section>
    </div>
  );
}
