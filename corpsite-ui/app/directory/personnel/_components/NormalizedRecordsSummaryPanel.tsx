"use client";

import * as React from "react";

import {
  getNormalizedRecordsSummary,
  getTrainingBatchReviewSummary,
  mapImportApiError,
  NORMALIZED_RECORD_KINDS,
  NORMALIZED_RECORD_KIND_SUMMARY_LABELS,
  type NormalizedRecordSummary,
  type TrainingBatchReviewSummary,
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
  const [training, setTraining] = React.useState<TrainingBatchReviewSummary | null>(null);

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
    void getTrainingBatchReviewSummary(batchId).then(setTraining).catch(() => setTraining(null));

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
      <section className="space-y-2 rounded-xl border border-amber-300 bg-amber-50/40 p-3 dark:border-amber-900 dark:bg-amber-950/20" data-testid="training-batch-summary">
        <h3 className="font-semibold">Обучение и повышение квалификации</h3>
        <p className="text-sm">Курсов: {training?.totals.courses ?? 0} · исходных ячеек: {training?.totals.source_cells ?? 0} · требуется ручное разделение: {training?.totals.manual_split ?? 0} · предварительно менее 144 часов: {training?.totals.below_144 ?? 0}</p>
        <div className="overflow-x-auto"><table className="min-w-full text-sm"><thead><tr className="border-b text-left"><th className="p-2">Сотрудник</th><th className="p-2">Курсы</th><th className="p-2">Подтверждено</th><th className="p-2">Предварительно</th><th className="p-2">До 144</th><th className="p-2">Состояние</th><th className="p-2">Действие</th></tr></thead><tbody>{training?.employees.map(row=><tr key={row.employee_id} className="border-b"><td className="p-2">#{row.employee_id}</td><td className="p-2">{row.course_count}</td><td className="p-2">{row.confirmed_hours_last_5y}</td><td className="p-2">{row.preliminary_hours_last_5y}</td><td className="p-2">{row.hours_missing}</td><td className="p-2">{row.state}</td><td className="p-2"><a className="underline" href={row.training_url}>Открыть обучение</a></td></tr>)}</tbody></table></div>
      </section>
    </section>
  );
}
