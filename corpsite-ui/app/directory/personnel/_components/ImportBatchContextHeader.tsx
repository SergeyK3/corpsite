"use client";

import * as React from "react";

import {
  getImportBatch,
  listImportBatches,
  mapImportApiError,
  type ImportBatchRow,
} from "../_lib/importApi.client";
import {
  formatImportBatchDateTime,
  formatImportBatchDropdownLabel,
  formatImportBatchLabel,
  formatImportBatchStatus,
  formatImportReportPeriod,
} from "../_lib/importBatchDisplay";

type Props = {
  batchId: number;
  className?: string;
  selectable?: boolean;
  onBatchChange?: (batchId: number) => void;
};

export default function ImportBatchContextHeader({
  batchId,
  className = "",
  selectable = false,
  onBatchChange,
}: Props) {
  const [batch, setBatch] = React.useState<ImportBatchRow | null>(null);
  const [batchOptions, setBatchOptions] = React.useState<ImportBatchRow[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);

    const load = selectable
      ? listImportBatches().then((data) => {
          if (cancelled) return null;
          setBatchOptions(data.items);
          const selected = data.items.find((item) => item.batch_id === batchId) ?? null;
          if (selected) {
            setBatch(selected);
            setError(null);
            return selected;
          }
          return getImportBatch(batchId);
        })
      : getImportBatch(batchId);

    void Promise.resolve(load)
      .then((data) => {
        if (cancelled) return;
        if (data) {
          setBatch(data);
          setError(null);
        } else {
          setBatch(null);
          setError("Импорт не найден");
        }
      })
      .catch((e) => {
        if (cancelled) return;
        setBatch(null);
        setError(mapImportApiError(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [batchId, selectable]);

  const handleSelectChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const nextBatchId = Number(event.target.value);
    if (!Number.isFinite(nextBatchId) || nextBatchId <= 0) return;
    const nextBatch = batchOptions.find((item) => item.batch_id === nextBatchId) ?? null;
    if (nextBatch) {
      setBatch(nextBatch);
      setError(null);
    }
    onBatchChange?.(nextBatchId);
  };

  return (
    <div
      className={[
        "rounded-xl border border-zinc-200 bg-zinc-50 px-4 py-3 dark:border-zinc-800 dark:bg-zinc-900/40",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      data-testid="import-batch-context-header"
      data-batch-id={batchId}
    >
      {selectable ? (
        <>
          <label className="block text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-500">
            Импорт для аналитики
            <select
              value={batchId}
              onChange={handleSelectChange}
              disabled={loading || batchOptions.length === 0}
              className="mt-2 block w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
              data-testid="import-batch-selector"
            >
              {batchOptions.length === 0 ? (
                <option value={batchId}>{batch ? formatImportBatchDropdownLabel(batch) : `Импорт ${batchId}`}</option>
              ) : (
                batchOptions.map((item) => (
                  <option key={item.batch_id} value={item.batch_id}>
                    {formatImportBatchDropdownLabel(item)}
                  </option>
                ))
              )}
            </select>
          </label>
          {loading ? (
            <p className="mt-2 text-sm text-zinc-500">Загрузка списка импортов…</p>
          ) : error ? (
            <p className="mt-2 text-sm text-red-600 dark:text-red-400">{error}</p>
          ) : batch ? (
            <p className="mt-2 text-xs text-zinc-500">
              {formatImportBatchStatus(batch.status)}
              {batch.technical_filename ? ` · ${batch.technical_filename}` : ""}
              {batch.byte_size != null ? ` · ${batch.byte_size.toLocaleString("ru-RU")} байт` : ""}
            </p>
          ) : null}
        </>
      ) : (
        <>
          <div className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
            {batch ? formatImportBatchLabel(batch) : `Импорт ${batchId}`}
          </div>
          {loading ? (
            <p className="mt-1 text-sm text-zinc-500">Загрузка сведений об импорте…</p>
          ) : error ? (
            <p className="mt-1 text-sm text-red-600 dark:text-red-400">{error}</p>
          ) : batch ? (
            <>
              <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
                <span className="font-medium text-zinc-800 dark:text-zinc-200">
                  {batch.original_filename || batch.file_name}
                </span>
                <span className="mx-2 text-zinc-300 dark:text-zinc-600">·</span>
                <span>{formatImportReportPeriod(batch.report_period || batch.report_month)}</span>
                <span className="mx-2 text-zinc-300 dark:text-zinc-600">·</span>
                <span>загружен {formatImportBatchDateTime(batch.imported_at)}</span>
              </p>
              {batch.technical_filename ? (
                <p className="mt-1 text-xs text-zinc-500">
                  Техническое имя: {batch.technical_filename}
                  {batch.byte_size != null ? ` · ${batch.byte_size.toLocaleString("ru-RU")} байт` : ""}
                  {batch.status ? ` · ${formatImportBatchStatus(batch.status)}` : ""}
                </p>
              ) : null}
            </>
          ) : null}
        </>
      )}
    </div>
  );
}
