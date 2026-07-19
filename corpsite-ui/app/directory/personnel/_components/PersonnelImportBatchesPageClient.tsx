"use client";

import * as React from "react";
import Link from "next/link";

import {
  deleteImportBatch,
  listImportBatches,
  listInitialBaselineSourceSelections,
  mapImportApiError,
  setInitialBaselineSourceSelection,
  type ImportBatchRow,
} from "../_lib/importApi.client";
import {
  buildInitialBaselineSourceByPeriod,
  buildInitialBaselineSourceIndex,
  isInitialBaselineSourceRow,
  reportPeriodIsoFromBatch,
  resolveInitialBaselineSourceSelectionForPeriod,
  type InitialBaselineSourceSelection,
} from "../_lib/initialBaselineSource";
import CanonicalSnapshotExportButton from "./CanonicalSnapshotExportButton";
import PersonnelBaselinesJournalSection from "./PersonnelBaselinesJournalSection";
import {
  formatImportBatchDateTime,
  formatImportBatchNumber,
  formatImportBatchStatus,
  formatImportReportPeriod,
} from "../_lib/importBatchDisplay";

export default function PersonnelImportBatchesPageClient() {
  const [items, setItems] = React.useState<ImportBatchRow[]>([]);
  const [sourceByPeriod, setSourceByPeriod] = React.useState<Map<string, number>>(new Map());
  const [selectionByPeriod, setSelectionByPeriod] = React.useState<
    Map<string, InitialBaselineSourceSelection>
  >(new Map());
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [actingBatchId, setActingBatchId] = React.useState<number | null>(null);
  const [selectingBatchId, setSelectingBatchId] = React.useState<number | null>(null);

  const loadPageData = React.useCallback(async () => {
    setLoading(true);
    try {
      const [batchData, selectionData] = await Promise.all([
        listImportBatches(),
        listInitialBaselineSourceSelections(),
      ]);
      setItems(batchData.items);
      setSelectionByPeriod(buildInitialBaselineSourceIndex(selectionData.items));
      setSourceByPeriod(buildInitialBaselineSourceByPeriod(selectionData.items));
      setError(null);
    } catch (e) {
      setError(mapImportApiError(e));
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void loadPageData();
  }, [loadPageData]);

  React.useEffect(() => {
    if (typeof window === "undefined" || window.location.hash !== "#baselines") return;
    window.requestAnimationFrame(() => {
      document.getElementById("baselines")?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }, [loading]);

  async function handleDelete(batch: ImportBatchRow) {
    const code = formatImportBatchNumber(batch);
    const ok = window.confirm(
      `Удалить импорт ${code} (${batch.original_filename || batch.file_name})?\n\nБудут удалены staging-данные и сохранённый файл. Доступно только для неприменённых импортов.`
    );
    if (!ok) return;
    setActingBatchId(batch.batch_id);
    try {
      await deleteImportBatch(batch.batch_id);
      setItems((prev) => prev.filter((row) => row.batch_id !== batch.batch_id));
      setSourceByPeriod((prev) => {
        const next = new Map(prev);
        for (const [period, batchId] of prev.entries()) {
          if (batchId === batch.batch_id) {
            next.delete(period);
          }
        }
        return next;
      });
      setSelectionByPeriod((prev) => {
        const next = new Map(prev);
        for (const [period, selection] of prev.entries()) {
          if (selection.source_batch_id === batch.batch_id) {
            next.delete(period);
          }
        }
        return next;
      });
      setError(null);
    } catch (e) {
      setError(mapImportApiError(e));
    } finally {
      setActingBatchId(null);
    }
  }

  async function handleSelectForBaseline(batch: ImportBatchRow) {
    const reportPeriod = reportPeriodIsoFromBatch(batch);
    if (!reportPeriod) {
      setError("Не удалось определить отчётный период импорта.");
      return;
    }
    setSelectingBatchId(batch.batch_id);
    try {
      const selection = await setInitialBaselineSourceSelection({
        report_period: reportPeriod,
        source_batch_id: batch.batch_id,
      });
      setSourceByPeriod((prev) => {
        const next = new Map(prev);
        next.set(selection.report_period.slice(0, 10), selection.source_batch_id);
        return next;
      });
      setSelectionByPeriod((prev) => {
        const next = new Map(prev);
        next.set(selection.report_period.slice(0, 10), selection);
        return next;
      });
      setError(null);
    } catch (e) {
      setError(mapImportApiError(e));
    } finally {
      setSelectingBatchId(null);
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
              <th className="px-4 py-3">Импорт</th>
              <th className="px-4 py-3">Отчётный период</th>
              <th className="px-4 py-3">Исходный файл</th>
              <th className="px-4 py-3">Дата изменения исходного файла</th>
              <th className="px-4 py-3">Дата загрузки</th>
              <th className="px-4 py-3">Статус</th>
              <th className="px-4 py-3">Всего строк</th>
              <th className="px-4 py-3">Ошибок</th>
              <th className="px-4 py-3">Для эталона</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={10} className="px-4 py-8 text-center text-zinc-500">
                  Загрузка…
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={10} className="px-4 py-8 text-center text-zinc-500">
                  Импорты не найдены. Загрузите файл контрольныйYYMM.xlsx или выполните CLI stage-import.
                </td>
              </tr>
            ) : (
              items.map((row) => {
                const periodSelection = resolveInitialBaselineSourceSelectionForPeriod(row, selectionByPeriod);
                const isSelected = isInitialBaselineSourceRow(row, sourceByPeriod);
                const periodIso = reportPeriodIsoFromBatch(row);
                const canSelect = Boolean(periodIso) && (periodSelection?.mutable ?? true);
                return (
                  <tr key={row.batch_id} className="border-t border-zinc-100 dark:border-zinc-800">
                    <td className="px-4 py-3 font-medium">
                      <Link
                        href={`/directory/personnel/import/${row.batch_id}`}
                        className="text-blue-600 hover:underline dark:text-blue-400"
                        data-testid={`import-batch-number-${row.batch_id}`}
                      >
                        {formatImportBatchNumber(row)}
                      </Link>
                    </td>
                    <td className="px-4 py-3">{formatImportReportPeriod(row.report_period || row.report_month)}</td>
                    <td className="px-4 py-3">{row.original_filename || row.file_name}</td>
                    <td className="px-4 py-3">{formatImportBatchDateTime(row.source_last_modified_at)}</td>
                    <td className="px-4 py-3">{formatImportBatchDateTime(row.imported_at)}</td>
                    <td className="px-4 py-3">{formatImportBatchStatus(row.status)}</td>
                    <td className="px-4 py-3">{row.total_rows}</td>
                    <td className="px-4 py-3">{row.error_rows}</td>
                    <td className="px-4 py-3">
                      {isSelected ? (
                        <span
                          className="inline-flex items-center rounded-full border border-green-200 bg-green-50 px-2.5 py-1 text-xs font-medium text-green-800 dark:border-green-900 dark:bg-green-950 dark:text-green-200"
                          data-testid={`initial-baseline-selected-${row.batch_id}`}
                        >
                          ✓ Выбран
                        </span>
                      ) : periodSelection?.lifecycle_status === "CONSUMED" &&
                        periodSelection.source_batch_id === row.batch_id ? (
                        <span
                          className="text-xs text-zinc-500"
                          data-testid={`initial-baseline-consumed-${row.batch_id}`}
                        >
                          Использован для MRD #{periodSelection.consumed_mrd_id}
                        </span>
                      ) : periodSelection?.mutable === false &&
                        periodSelection.source_batch_id === row.batch_id ? (
                        <span
                          className="text-xs text-zinc-500"
                          data-testid={`initial-baseline-frozen-${row.batch_id}`}
                        >
                          Зафиксирован
                        </span>
                      ) : canSelect ? (
                        <button
                          type="button"
                          className="rounded-lg border border-zinc-200 px-2.5 py-1 text-xs font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-900"
                          disabled={selectingBatchId === row.batch_id}
                          data-testid={`initial-baseline-select-${row.batch_id}`}
                          onClick={() => void handleSelectForBaseline(row)}
                        >
                          {selectingBatchId === row.batch_id ? "Выбор…" : "Выбрать"}
                        </button>
                      ) : (
                        <span className="text-xs text-zinc-400">—</span>
                      )}
                    </td>
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
                          Обучение
                        </Link>
                        {row.can_delete ? (
                          <button
                            type="button"
                            disabled={actingBatchId === row.batch_id}
                            onClick={() => handleDelete(row)}
                            className="text-red-600 hover:underline disabled:opacity-50 dark:text-red-400"
                          >
                            {actingBatchId === row.batch_id ? "Удаление…" : "Удалить"}
                          </button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      <PersonnelBaselinesJournalSection anchorId="baselines" embedded initialBaselineSourceByPeriod={sourceByPeriod} />
    </div>
  );
}
