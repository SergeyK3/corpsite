// FILE: corpsite-ui/app/directory/personnel/_components/PersonnelImportBatchesPageClient.tsx
"use client";

import * as React from "react";
import Link from "next/link";

import {
  deleteImportBatch,
  listImportBatches,
  mapImportApiError,
  type ImportBatchRow,
} from "../_lib/importApi.client";
import CanonicalSnapshotExportButton from "./CanonicalSnapshotExportButton";

function fmtDate(value: string | null): string {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString("ru-RU");
  } catch {
    return value;
  }
}

export default function PersonnelImportBatchesPageClient() {
  const [items, setItems] = React.useState<ImportBatchRow[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [deletingId, setDeletingId] = React.useState<number | null>(null);

  const loadBatches = React.useCallback(async () => {
    setLoading(true);
    try {
      const data = await listImportBatches();
      setItems(data.items);
      setError(null);
    } catch (e) {
      setError(mapImportApiError(e));
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    loadBatches();
  }, [loadBatches]);

  async function handleDelete(batchId: number, fileName: string) {
    const ok = window.confirm(
      `Удалить batch #${batchId} (${fileName})?\n\nБудут удалены staging-строки и candidates. Сотрудники и employee_documents не затрагиваются.`
    );
    if (!ok) return;
    setDeletingId(batchId);
    try {
      await deleteImportBatch(batchId);
      setItems((prev) => prev.filter((row) => row.batch_id !== batchId));
      setError(null);
    } catch (e) {
      setError(mapImportApiError(e));
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="px-4 py-3">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">Импорт контрольного списка</h1>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
            Staging-данные из Excel. Без apply и без изменения сотрудников.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <CanonicalSnapshotExportButton />
          <Link
            href="/directory/personnel/import/upload"
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            Загрузить файл
          </Link>
        </div>
      </div>

      {error ? (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
          {error}
        </div>
      ) : null}

      <div className="overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800">
        <table className="min-w-full text-sm">
          <thead className="bg-zinc-50 text-left text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-500 dark:bg-zinc-900">
            <tr>
              <th className="px-4 py-3">Дата импорта</th>
              <th className="px-4 py-3">Файл</th>
              <th className="px-4 py-3">Статус</th>
              <th className="px-4 py-3">Всего строк</th>
              <th className="px-4 py-3">Ошибок</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-zinc-500">
                  Загрузка…
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-zinc-500">
                  Импорты не найдены. Загрузите файл или выполните CLI stage-import.
                </td>
              </tr>
            ) : (
              items.map((row) => (
                <tr key={row.batch_id} className="border-t border-zinc-100 dark:border-zinc-800">
                  <td className="px-4 py-3">{fmtDate(row.imported_at)}</td>
                  <td className="px-4 py-3">{row.file_name}</td>
                  <td className="px-4 py-3 font-mono text-xs">{row.status}</td>
                  <td className="px-4 py-3">{row.total_rows}</td>
                  <td className="px-4 py-3">{row.error_rows}</td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-3">
                      <Link
                        href={`/directory/personnel/import/${row.batch_id}`}
                        className="text-blue-600 hover:underline dark:text-blue-400"
                      >
                        Аналитика
                      </Link>
                      <Link
                        href={`/directory/personnel/import/${row.batch_id}/review`}
                        className="text-blue-600 hover:underline dark:text-blue-400"
                      >
                        Review
                      </Link>
                      <Link
                        href={`/directory/personnel/import/${row.batch_id}/training`}
                        className="text-blue-600 hover:underline dark:text-blue-400"
                      >
                        Документы
                      </Link>
                      <button
                        type="button"
                        disabled={deletingId === row.batch_id}
                        onClick={() => handleDelete(row.batch_id, row.file_name)}
                        className="text-red-600 hover:underline disabled:opacity-50 dark:text-red-400"
                      >
                        {deletingId === row.batch_id ? "Удаление…" : "Удалить"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
