"use client";

import * as React from "react";

import {
  getNormalizedRecordsSummary,
  mapImportApiError,
  NORMALIZED_RECORD_KINDS,
  NORMALIZED_RECORD_KIND_SUMMARY_LABELS,
  type NormalizedRecordSummary,
} from "../_lib/importApi.client";

function SummaryCard({
  label,
  value,
  testId,
}: {
  label: string;
  value: number;
  testId?: string;
}) {
  return (
    <div
      className="rounded-xl border border-zinc-200 bg-white px-4 py-3 dark:border-zinc-800 dark:bg-zinc-950"
      data-testid={testId}
    >
      <div className="text-xs font-medium uppercase tracking-wide text-zinc-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-zinc-900 dark:text-zinc-100">{value}</div>
    </div>
  );
}

type Props = {
  batchId: number;
};

export default function NormalizedRecordsSummaryPanel({ batchId }: Props) {
  const [summaryLoading, setSummaryLoading] = React.useState(true);
  const [summary, setSummary] = React.useState<NormalizedRecordSummary | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    setSummaryLoading(true);
    getNormalizedRecordsSummary(batchId)
      .then((data) => {
        if (cancelled) return;
        setSummary(data);
        setError(null);
      })
      .catch((e) => {
        if (cancelled) return;
        setSummary(null);
        setError(mapImportApiError(e));
      })
      .finally(() => {
        if (!cancelled) setSummaryLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [batchId]);

  const kindCards = NORMALIZED_RECORD_KINDS.map((key) => ({
    key,
    label: NORMALIZED_RECORD_KIND_SUMMARY_LABELS[key],
  }));

  return (
    <section className="space-y-3" data-testid="normalized-records-summary">
      {error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
          {error}
        </div>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <SummaryCard label="Всего" value={summary?.total ?? 0} testId="normalized-summary-total" />
        <SummaryCard label="Ожидают проверки" value={summary?.pending ?? 0} testId="normalized-summary-pending" />
        <SummaryCard label="Утверждено" value={summary?.approved ?? 0} testId="normalized-summary-approved" />
        <SummaryCard label="Отклонено" value={summary?.rejected ?? 0} testId="normalized-summary-rejected" />
        <SummaryCard label="Промотировано" value={summary?.promoted ?? 0} testId="normalized-summary-promoted" />
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {kindCards.map((card) => (
          <SummaryCard
            key={card.key}
            label={card.label}
            value={summary?.by_kind?.[card.key] ?? 0}
            testId={`normalized-summary-kind-${card.key}`}
          />
        ))}
      </div>

      {summaryLoading ? <div className="text-xs text-zinc-500">Обновление сводки…</div> : null}
      {summary?.skipped ? (
        <div className="text-sm text-amber-700 dark:text-amber-300">
          Таблица нормализованных записей недоступна — примените миграцию ADR-039 Phase 3B.
        </div>
      ) : null}
    </section>
  );
}
