"use client";

import * as React from "react";

import { getImportBatch, mapImportApiError, type ImportBatchRow } from "../_lib/importApi.client";
import { formatImportBatchDateTime, formatImportBatchLabel } from "../_lib/importBatchDisplay";

type Props = {
  batchId: number;
  className?: string;
};

export default function ImportBatchContextHeader({ batchId, className = "" }: Props) {
  const [batch, setBatch] = React.useState<ImportBatchRow | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    void getImportBatch(batchId)
      .then((data) => {
        if (cancelled) return;
        setBatch(data);
        setError(data ? null : "Импорт не найден");
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
  }, [batchId]);

  return (
    <div
      className={["rounded-xl border border-zinc-200 bg-zinc-50 px-4 py-3 dark:border-zinc-800 dark:bg-zinc-900/40", className]
        .filter(Boolean)
        .join(" ")}
      data-testid="import-batch-context-header"
      data-batch-id={batchId}
    >
      <div className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
        {formatImportBatchLabel(batchId)}
      </div>
      {loading ? (
        <p className="mt-1 text-sm text-zinc-500">Загрузка сведений об импорте…</p>
      ) : error ? (
        <p className="mt-1 text-sm text-red-600 dark:text-red-400">{error}</p>
      ) : batch ? (
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          <span className="font-medium text-zinc-800 dark:text-zinc-200">{batch.file_name}</span>
          <span className="mx-2 text-zinc-300 dark:text-zinc-600">·</span>
          <span>{formatImportBatchDateTime(batch.imported_at)}</span>
        </p>
      ) : null}
    </div>
  );
}
