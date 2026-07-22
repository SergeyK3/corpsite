"use client";

import * as React from "react";

import {
  getImportTrainingDateQualityReport,
  mapImportApiError,
  stagingRowExceptionKey,
  type TrainingDateQualityItem,
} from "../_lib/importApi.client";
import { getNormalizedRecordKindLabel } from "../_lib/normalizedRecordLabels";

type Props = {
  batchId: number;
  refreshKey?: number;
  onOpenRow?: (rowId: number) => void;
  onOpenNormalized?: (normalizedRecordId: number) => void;
};

function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("ru-RU");
}

export default function ImportTrainingDateQualityPanel({
  batchId,
  refreshKey = 0,
  onOpenRow,
  onOpenNormalized,
}: Props) {
  const [items, setItems] = React.useState<TrainingDateQualityItem[]>([]);
  const [total, setTotal] = React.useState(0);
  const [remark, setRemark] = React.useState("");
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [expanded, setExpanded] = React.useState(true);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    void getImportTrainingDateQualityReport(batchId, { limit: 500 })
      .then((report) => {
        if (cancelled) return;
        setItems(report.items);
        setTotal(report.total);
        setRemark(report.remark);
      })
      .catch((e) => {
        if (cancelled) return;
        setItems([]);
        setTotal(0);
        setError(mapImportApiError(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [batchId, refreshKey]);

  return (
    <section
      className="mb-4 rounded-xl border border-amber-200 bg-amber-50/40 dark:border-amber-900/50 dark:bg-amber-950/20"
      data-testid="import-training-date-quality-panel"
    >
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        className="flex w-full items-start justify-between gap-3 px-4 py-3 text-left"
      >
        <div>
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
            Неполные даты обучения
          </h3>
          <p className="mt-0.5 text-xs text-zinc-600 dark:text-zinc-400">
            Отчёт для постепенного уточнения дат обучения и образования. Импорт не блокируется.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="rounded-full border border-amber-300 bg-white px-2.5 py-0.5 text-xs font-medium text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100">
            {loading ? "…" : total.toLocaleString("ru-RU")}
          </span>
          <span className="text-xs text-zinc-500">{expanded ? "Свернуть" : "Развернуть"}</span>
        </div>
      </button>

      {expanded ? (
        <div className="border-t border-amber-200/80 px-4 py-3 dark:border-amber-900/40">
          {loading ? (
            <p className="text-sm text-zinc-500">Загрузка отчёта…</p>
          ) : error ? (
            <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
          ) : total === 0 ? (
            <p className="text-sm text-zinc-600 dark:text-zinc-400">
              Записей с неполными датами обучения не обнаружено.
            </p>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-amber-200/80 bg-white dark:border-amber-900/40 dark:bg-zinc-950">
              <table className="min-w-full text-sm">
                <thead className="bg-amber-100/60 text-left text-[11px] uppercase tracking-wide text-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
                  <tr>
                    <th className="px-3 py-2">Сотрудник</th>
                    <th className="px-3 py-2">Отделение</th>
                    <th className="px-3 py-2">Запись</th>
                    <th className="px-3 py-2">Даты</th>
                    <th className="px-3 py-2">Замечание</th>
                    <th className="px-3 py-2">Действие</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => {
                    const key = `${item.row_id ?? "row"}-${item.normalized_record_id ?? "nr"}`;
                    const recordLabel =
                      item.record_kind === "roster"
                        ? "Состав"
                        : getNormalizedRecordKindLabel(item.record_kind, item.record_kind);
                    return (
                      <tr
                        key={key}
                        className="border-t border-amber-100 dark:border-amber-900/30"
                      >
                        <td className="px-3 py-2">
                          <div className="font-medium text-zinc-900 dark:text-zinc-100">
                            {item.full_name || "—"}
                          </div>
                          {item.position_raw ? (
                            <div className="text-xs text-zinc-500">{item.position_raw}</div>
                          ) : null}
                        </td>
                        <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">
                          {item.department || "—"}
                        </td>
                        <td className="px-3 py-2">
                          <div className="text-zinc-800 dark:text-zinc-200">
                            {item.record_title || recordLabel}
                          </div>
                          {item.source_text ? (
                            <div className="mt-0.5 text-xs text-zinc-500">{item.source_text}</div>
                          ) : null}
                        </td>
                        <td className="px-3 py-2 text-xs text-zinc-600 dark:text-zinc-400">
                          {item.start_date || item.end_date || item.issue_date ? (
                            <div className="space-y-0.5">
                              {item.start_date ? <div>Начало: {formatDate(item.start_date)}</div> : null}
                              {item.end_date ? <div>Окончание: {formatDate(item.end_date)}</div> : null}
                              {item.issue_date ? <div>Выдача: {formatDate(item.issue_date)}</div> : null}
                            </div>
                          ) : (
                            "—"
                          )}
                        </td>
                        <td className="px-3 py-2 text-amber-800 dark:text-amber-200">
                          {item.remarks.join("; ") || remark}
                        </td>
                        <td className="px-3 py-2">
                          {item.normalized_record_id != null && onOpenNormalized ? (
                            <button
                              type="button"
                              onClick={() => onOpenNormalized(item.normalized_record_id!)}
                              className="text-xs font-medium text-blue-700 hover:underline dark:text-blue-300"
                            >
                              Открыть запись
                            </button>
                          ) : item.row_id != null && onOpenRow ? (
                            <button
                              type="button"
                              onClick={() => onOpenRow(item.row_id!)}
                              className="text-xs font-medium text-blue-700 hover:underline dark:text-blue-300"
                            >
                              Открыть строку
                            </button>
                          ) : (
                            "—"
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : null}
    </section>
  );
}
