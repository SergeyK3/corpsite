"use client";

import * as React from "react";
import Link from "next/link";

import ImportMonthlyDiffRemovedSection from "./ImportMonthlyDiffRemovedSection";
import ImportReviewByExceptionBanner from "./ImportReviewByExceptionBanner";
import CanonicalSnapshotExportButton from "./CanonicalSnapshotExportButton";
import { buildHrChangeEventsHref } from "../_lib/hrChangeEventsApi.client";
import {
  computeImportBatchDiff,
  getImportBatchDiffSummary,
  mapImportApiError,
  type ImportBatchDiffSummary,
  type ImportBatchReviewVisibility,
} from "../_lib/importApi.client";
import {
  MONTHLY_DIFF_STATUSES,
  MONTHLY_DIFF_STATUS_SUMMARY_LABELS,
} from "../_lib/monthlyDiffLabels";

function SummaryCountCard({
  label,
  value,
  muted,
}: {
  label: string;
  value: number;
  muted?: boolean;
}) {
  return (
    <div
      className={`rounded-xl border px-3 py-2 ${
        muted
          ? "border-zinc-200 bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900/40"
          : "border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950"
      }`}
    >
      <div className="text-[11px] font-medium uppercase tracking-wide text-zinc-500">{label}</div>
      <div
        className={`mt-0.5 text-xl font-semibold ${
          muted ? "text-zinc-500" : "text-zinc-900 dark:text-zinc-100"
        }`}
      >
        {value.toLocaleString("ru-RU")}
      </div>
    </div>
  );
}

type Props = {
  batchId: number;
  showUnchanged: boolean;
  onShowUnchangedChange: (value: boolean) => void;
  onSummaryLoaded?: (summary: ImportBatchDiffSummary | null) => void;
  onRecomputed?: () => void;
};

export default function ImportMonthlyDiffSummaryPanel({
  batchId,
  showUnchanged,
  onShowUnchangedChange,
  onSummaryLoaded,
  onRecomputed,
}: Props) {
  const [loading, setLoading] = React.useState(true);
  const [recomputing, setRecomputing] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [summary, setSummary] = React.useState<ImportBatchDiffSummary | null>(null);

  const loadSummary = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getImportBatchDiffSummary(batchId);
      setSummary(data);
      onSummaryLoaded?.(data);
    } catch (e) {
      setError(mapImportApiError(e));
      setSummary(null);
      onSummaryLoaded?.(null);
    } finally {
      setLoading(false);
    }
  }, [batchId, onSummaryLoaded]);

  React.useEffect(() => {
    if (batchId > 0) {
      loadSummary();
    }
  }, [batchId, loadSummary]);

  async function handleRecompute() {
    setRecomputing(true);
    setError(null);
    try {
      await computeImportBatchDiff(batchId);
      await loadSummary();
      onRecomputed?.();
    } catch (e) {
      setError(mapImportApiError(e));
    } finally {
      setRecomputing(false);
    }
  }

  if (loading) {
    return (
      <section className="mb-4 rounded-xl border border-zinc-200 px-4 py-3 text-sm text-zinc-500 dark:border-zinc-800">
        Загрузка сводки diff…
      </section>
    );
  }

  if (summary?.skipped) {
    return (
      <section className="mb-4 rounded-xl border border-amber-200 bg-amber-50/50 px-4 py-3 text-sm text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/20 dark:text-amber-200">
        Monthly diff недоступен — примените миграцию ADR-040 Phase B.
      </section>
    );
  }

  const counts = summary?.summary ?? {};
  const visibility: ImportBatchReviewVisibility | undefined = summary?.review_visibility;
  const computedLabel = summary?.computed_at
    ? new Date(summary.computed_at).toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" })
    : null;

  return (
    <section className="mb-4 space-y-3 rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
      <ImportReviewByExceptionBanner visibility={visibility ?? null} />

      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
            Сравнение с каноническим эталоном
          </h2>
          <p className="mt-1 text-xs text-zinc-500">
            {summary?.snapshot_id
              ? `Эталон snapshot #${summary.snapshot_id}`
              : "Активный эталон не найден — все записи помечены как новые"}
            {computedLabel ? ` · diff: ${computedLabel}` : ""}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <CanonicalSnapshotExportButton />
          <Link
            href={buildHrChangeEventsHref({ source_batch_id: batchId })}
            className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm font-medium text-zinc-800 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-900"
          >
            История изменений batch
          </Link>
          <label className="flex items-center gap-2 text-sm text-zinc-700 dark:text-zinc-300">
            <input
              type="checkbox"
              checked={showUnchanged}
              onChange={(e) => onShowUnchangedChange(e.target.checked)}
              className="rounded border-zinc-300 dark:border-zinc-700"
            />
            Показывать неизменённые записи
          </label>
          <button
            type="button"
            onClick={handleRecompute}
            disabled={recomputing}
            className="rounded-lg border border-blue-300 bg-blue-50 px-3 py-1.5 text-sm font-medium text-blue-900 hover:bg-blue-100 disabled:opacity-50 dark:border-blue-900 dark:bg-blue-950/40 dark:text-blue-100"
          >
            {recomputing ? "Пересчёт…" : "Пересчитать diff"}
          </button>
        </div>
      </div>

      {error ? <div className="text-sm text-red-600">{error}</div> : null}

      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <SummaryCountCard label="Visible records" value={visibility?.visible_records ?? 0} />
        <SummaryCountCard
          label="Hidden unchanged"
          value={visibility?.hidden_unchanged ?? counts.UNCHANGED ?? 0}
          muted
        />
        {!showUnchanged && (visibility?.hidden_unchanged ?? 0) > 0 ? (
          <div className="flex items-center rounded-xl border border-dashed border-zinc-300 px-3 py-2 text-xs text-zinc-500 sm:col-span-2 dark:border-zinc-700">
            По умолчанию записи со статусом «Без изменений» скрыты из review-списков.
          </div>
        ) : null}
      </div>

      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
        {MONTHLY_DIFF_STATUSES.map((status) => (
          <SummaryCountCard
            key={status}
            label={
              status === "UNCHANGED" && !showUnchanged
                ? `${MONTHLY_DIFF_STATUS_SUMMARY_LABELS[status]} (hidden)`
                : MONTHLY_DIFF_STATUS_SUMMARY_LABELS[status]
            }
            value={counts[status] ?? 0}
            muted={status === "UNCHANGED" && !showUnchanged}
          />
        ))}
      </div>

      <ImportMonthlyDiffRemovedSection items={summary?.removed ?? []} />
    </section>
  );
}
