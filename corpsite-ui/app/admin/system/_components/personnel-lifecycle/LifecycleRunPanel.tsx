// FILE: corpsite-ui/app/admin/system/_components/personnel-lifecycle/LifecycleRunPanel.tsx
"use client";

import { useState } from "react";

import {
  executeLifecycleRun,
  mapPersonnelLifecycleApiError,
  previewLifecycleRun,
  type LifecycleRunReport,
} from "../../_lib/personnelLifecycleApi.client";
import { formatDurationMs } from "../../_lib/personnelLifecycleLabels";
import ErrorBanner, { SuccessBanner } from "../shared/ErrorBanner";
import JsonViewer from "../shared/JsonViewer";
import ConfirmDialog from "../shared/ConfirmDialog";

type LifecycleRunPanelProps = {
  onRunComplete?: () => void;
};

export default function LifecycleRunPanel({ onRunComplete }: LifecycleRunPanelProps) {
  const [previousSnapshotId, setPreviousSnapshotId] = useState("");
  const [snapshotId, setSnapshotId] = useState("");
  const [refreshCache, setRefreshCache] = useState(true);
  const [enqueue, setEnqueue] = useState(false);
  const [syncPersons, setSyncPersons] = useState(false);
  const [report, setReport] = useState<LifecycleRunReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [executeConfirm, setExecuteConfirm] = useState(false);

  function parseRequest() {
    const previous = Number(previousSnapshotId);
    const current = Number(snapshotId);
    if (!Number.isFinite(previous) || previous < 1 || !Number.isFinite(current) || current < 1) {
      throw new Error("Укажите корректные snapshot ID (целые числа ≥ 1)");
    }
    if (previous === current) {
      throw new Error("previous snapshot и current snapshot должны отличаться");
    }
    return {
      previous_snapshot_id: previous,
      snapshot_id: current,
      refresh_cache: refreshCache,
      enqueue,
      sync_persons: syncPersons,
    };
  }

  async function handlePreview(): Promise<void> {
    setLoading(true);
    setError(null);
    setSuccess(null);
    try {
      const body = parseRequest();
      const result = await previewLifecycleRun(body);
      setReport(result);
      setSuccess(`Preview завершён: ${result.run_status} (${formatDurationMs(result.duration_ms)})`);
    } catch (err) {
      setReport(null);
      setError(mapPersonnelLifecycleApiError(err, "Preview не удался"));
    } finally {
      setLoading(false);
    }
  }

  async function handleExecute(): Promise<void> {
    setExecuteConfirm(false);
    setLoading(true);
    setError(null);
    setSuccess(null);
    try {
      const body = parseRequest();
      const result = await executeLifecycleRun(body);
      setReport(result);
      setSuccess(
        `Execute завершён: run #${result.run_id ?? "—"}, ${result.run_status} (${formatDurationMs(result.duration_ms)})`,
      );
      onRunComplete?.();
    } catch (err) {
      setError(mapPersonnelLifecycleApiError(err, "Execute не удался"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="space-y-4" data-testid="lifecycle-run-panel">
      <h2 className="text-lg font-semibold">Ежемесячный запуск цикла</h2>
      <ErrorBanner message={error} />
      <SuccessBanner message={success} />

      <div className="grid gap-3 rounded-lg border border-zinc-200 p-4 sm:grid-cols-2 lg:grid-cols-3 dark:border-zinc-700">
        <label className="text-xs">
          предыдущий снимок
          <input
            type="number"
            min={1}
            value={previousSnapshotId}
            onChange={(e) => setPreviousSnapshotId(e.target.value)}
            className="mt-1 w-full rounded border px-2 py-1 dark:border-zinc-600 dark:bg-zinc-900"
            data-testid="lifecycle-run-previous-snapshot"
          />
        </label>
        <label className="text-xs">
          текущий снимок
          <input
            type="number"
            min={1}
            value={snapshotId}
            onChange={(e) => setSnapshotId(e.target.value)}
            className="mt-1 w-full rounded border px-2 py-1 dark:border-zinc-600 dark:bg-zinc-900"
            data-testid="lifecycle-run-current-snapshot"
          />
        </label>
        <div className="flex flex-col justify-end gap-2 text-xs">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={refreshCache}
              onChange={(e) => setRefreshCache(e.target.checked)}
            />
            обновить кэш
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={enqueue} onChange={(e) => setEnqueue(e.target.checked)} />
            поставить в очередь
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={syncPersons}
              onChange={(e) => setSyncPersons(e.target.checked)}
            />
            синхронизировать персон
          </label>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={loading}
          onClick={() => void handlePreview()}
          className="rounded-lg bg-zinc-800 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-200 dark:text-zinc-900"
          data-testid="lifecycle-run-preview-btn"
        >
          {loading ? "…" : "Предпросмотр"}
        </button>
        <button
          type="button"
          disabled={loading}
          onClick={() => setExecuteConfirm(true)}
          className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          data-testid="lifecycle-run-execute-btn"
        >
          Выполнить
        </button>
      </div>

      {report ? (
        <div className="space-y-4 rounded-lg border border-zinc-200 p-4 dark:border-zinc-700" data-testid="lifecycle-run-report">
          <div className="flex flex-wrap gap-4 text-sm">
            <span>
              Статус: <strong>{report.run_status}</strong>
            </span>
            <span>
              Длительность: <strong>{formatDurationMs(report.duration_ms)}</strong>
            </span>
            {report.run_id != null ? (
              <span>
                ID запуска: <strong>#{report.run_id}</strong>
              </span>
            ) : null}
          </div>
          <JsonViewer title="effective cache" value={report.effective_cache} testId="lifecycle-report-effective-cache" />
          <JsonViewer title="monthly diff" value={report.monthly_diff} testId="lifecycle-report-monthly-diff" />
          <JsonViewer title="person sync" value={report.person_sync} testId="lifecycle-report-person-sync" />
          <JsonViewer title="validation" value={report.validation} testId="lifecycle-report-validation" />
          {report.warnings.length > 0 ? (
            <JsonViewer title="предупреждения" value={report.warnings} testId="lifecycle-report-warnings" />
          ) : null}
          {report.errors.length > 0 ? (
            <JsonViewer title="ошибки" value={report.errors} testId="lifecycle-report-errors" />
          ) : null}
        </div>
      ) : null}

      <ConfirmDialog
        open={executeConfirm}
        title="Выполнить lifecycle run?"
        message="Будет выполнен полный monthly lifecycle run (не preview). Продолжить?"
        confirmLabel="Выполнить"
        onConfirm={() => void handleExecute()}
        onCancel={() => setExecuteConfirm(false)}
      />
    </section>
  );
}
