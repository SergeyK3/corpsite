"use client";

import * as React from "react";

import {
  assessImportReviewProgress,
  mapImportApiError,
  type ImportReviewProgressAssessment,
} from "../_lib/importApi.client";
import {
  formatImportBatchStatus,
  isImportBatchReviewCompleted,
} from "../_lib/importBatchDisplay";
import { formatCompleteImportReviewBlockerSummary } from "../_lib/completeImportReview";

type Props = {
  batchId: number;
  importCode: string;
  batchStatus: string;
  refreshKey?: string | number;
  onStatusChanged?: () => void;
};

function MetricCard({
  label,
  value,
  highlight,
  testId,
}: {
  label: string;
  value: number;
  highlight?: boolean;
  testId: string;
}) {
  return (
    <div
      className={`rounded-xl border px-3 py-2 ${
        highlight
          ? "border-amber-300 bg-amber-50/70 dark:border-amber-900 dark:bg-amber-950/30"
          : "border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950"
      }`}
      data-testid={testId}
    >
      <div className="text-[11px] font-medium uppercase tracking-wide text-zinc-500">{label}</div>
      <div
        className={`mt-0.5 text-xl font-semibold ${
          highlight ? "text-amber-900 dark:text-amber-100" : "text-zinc-900 dark:text-zinc-100"
        }`}
      >
        {value.toLocaleString("ru-RU")}
      </div>
    </div>
  );
}

export default function ImportReviewProgressStrip({
  batchId,
  importCode,
  batchStatus,
  refreshKey = 0,
  onStatusChanged,
}: Props) {
  const [assessment, setAssessment] = React.useState<ImportReviewProgressAssessment | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const previousStatusRef = React.useRef(batchStatus);

  const load = React.useCallback(async () => {
    if (batchId <= 0) {
      setAssessment(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await assessImportReviewProgress(batchId);
      setAssessment(data);
      if (
        previousStatusRef.current !== data.batch_status &&
        isImportBatchReviewCompleted(data.batch_status)
      ) {
        onStatusChanged?.();
      }
      previousStatusRef.current = data.batch_status;
    } catch (e) {
      setError(mapImportApiError(e));
      setAssessment(null);
    } finally {
      setLoading(false);
    }
  }, [batchId, onStatusChanged]);

  React.useEffect(() => {
    void load();
  }, [load, refreshKey]);

  const progress = assessment?.review_progress;
  const reviewDone = isImportBatchReviewCompleted(assessment?.batch_status ?? batchStatus);
  const blockerSummary =
    assessment && !reviewDone && assessment.blockers.length > 0
      ? formatCompleteImportReviewBlockerSummary(assessment.blockers, {
          error_rows: progress?.error_rows ?? 0,
        })
      : null;

  return (
    <section
      className="mb-4 rounded-xl border border-zinc-200 p-4 dark:border-zinc-800"
      data-testid="import-review-progress-strip"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
            Готовность проверки импорта
          </h2>
          <p className="mt-1 text-xs text-zinc-500">
            Статус:{" "}
            <span className="font-medium text-zinc-700 dark:text-zinc-300">
              {formatImportBatchStatus(assessment?.batch_status ?? batchStatus)}
            </span>
            {reviewDone ? (
              <span className="ml-2 text-green-700 dark:text-green-300">
                · все очереди обработаны, переход выполнен автоматически
              </span>
            ) : null}
          </p>
        </div>
      </div>

      {loading ? <div className="mt-3 text-sm text-zinc-500">Загрузка показателей…</div> : null}
      {error ? <div className="mt-3 text-sm text-red-600">{error}</div> : null}

      {progress ? (
        <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            label="Необработанные normalized-записи"
            value={progress.pending_normalized}
            highlight={progress.pending_normalized > 0}
            testId="review-progress-pending-normalized"
          />
          <MetricCard
            label="Ошибки парсинга"
            value={progress.error_rows}
            highlight={progress.error_rows > 0}
            testId="review-progress-error-rows"
          />
          <MetricCard
            label="Отсутствуют в файле (без решения)"
            value={progress.pending_removals}
            highlight={progress.pending_removals > 0}
            testId="review-progress-pending-removals"
          />
          <div
            className={`rounded-xl border px-3 py-2 ${
              progress.ready
                ? "border-green-200 bg-green-50/70 dark:border-green-900 dark:bg-green-950/30"
                : "border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950"
            }`}
            data-testid="review-progress-ready"
          >
            <div className="text-[11px] font-medium uppercase tracking-wide text-zinc-500">Готовность</div>
            <div
              className={`mt-0.5 text-sm font-semibold ${
                progress.ready ? "text-green-900 dark:text-green-100" : "text-zinc-900 dark:text-zinc-100"
              }`}
            >
              {progress.ready ? "Готов к эталону" : "Ожидает проверки"}
            </div>
          </div>
        </div>
      ) : null}

      {blockerSummary ? (
        <p className="mt-3 text-sm text-amber-900 dark:text-amber-200" data-testid="review-progress-blockers">
          {blockerSummary}
        </p>
      ) : null}
    </section>
  );
}
