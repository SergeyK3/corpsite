// FILE: corpsite-ui/app/admin/system/_components/personnel-lifecycle/ValidationPanel.tsx
"use client";

import { useState } from "react";

import {
  fetchLifecycleValidation,
  mapPersonnelLifecycleApiError,
  type ValidationResponse,
} from "../../_lib/personnelLifecycleApi.client";
import {
  VALIDATION_CARD_CODES,
  findValidationCheck,
  validationSeverityClass,
} from "../../_lib/personnelLifecycleLabels";
import ErrorBanner from "../shared/ErrorBanner";
import JsonViewer from "../shared/JsonViewer";

const PRIMARY_CHECK_CODES = [
  "duplicate_active_overrides",
  "duplicate_active_assignments",
  "active_assignment_without_person",
  "personnel_events_stuck_detected",
  "outdated_effective_cache",
] as const;

export default function ValidationPanel() {
  const [previousSnapshotId, setPreviousSnapshotId] = useState("");
  const [snapshotId, setSnapshotId] = useState("");
  const [result, setResult] = useState<ValidationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleValidate(): Promise<void> {
    const previous = Number(previousSnapshotId);
    const current = Number(snapshotId);
    if (!Number.isFinite(previous) || previous < 1 || !Number.isFinite(current) || current < 1) {
      setError("Укажите корректные snapshot ID");
      return;
    }
    if (previous === current) {
      setError("previous_snapshot_id must differ from snapshot_id");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await fetchLifecycleValidation({
        previous_snapshot_id: previous,
        snapshot_id: current,
      });
      setResult(data);
    } catch (err) {
      setResult(null);
      setError(mapPersonnelLifecycleApiError(err, "Validation не удалась"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="space-y-4" data-testid="validation-panel">
      <h2 className="text-lg font-semibold">Проверка</h2>
      <ErrorBanner message={error} />

      <div className="flex flex-wrap items-end gap-3">
        <label className="text-xs">
          предыдущий снимок
          <input
            type="number"
            min={1}
            value={previousSnapshotId}
            onChange={(e) => setPreviousSnapshotId(e.target.value)}
            className="mt-1 block w-40 rounded border px-2 py-1 dark:border-zinc-600 dark:bg-zinc-900"
            data-testid="validation-previous-snapshot"
          />
        </label>
        <label className="text-xs">
          текущий снимок
          <input
            type="number"
            min={1}
            value={snapshotId}
            onChange={(e) => setSnapshotId(e.target.value)}
            className="mt-1 block w-40 rounded border px-2 py-1 dark:border-zinc-600 dark:bg-zinc-900"
            data-testid="validation-current-snapshot"
          />
        </label>
        <button
          type="button"
          disabled={loading}
          onClick={() => void handleValidate()}
          className="rounded-lg bg-zinc-800 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-200 dark:text-zinc-900"
          data-testid="validation-run-btn"
        >
          {loading ? "…" : "Проверить"}
        </button>
      </div>

      {!result ? (
        <p className="text-sm text-zinc-500" data-testid="validation-empty">
          Укажите пару снимков для post-lifecycle validation.
        </p>
      ) : (
        <div className="space-y-4" data-testid="validation-results">
          <div className="flex flex-wrap gap-4 text-sm">
            <span>предупреждения: {result.warnings_count}</span>
            <span>ошибки: {result.errors_count}</span>
            {result.validated_at ? <span>validated_at: {result.validated_at}</span> : null}
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {PRIMARY_CHECK_CODES.map((code) => {
              const check = findValidationCheck(result.checks, code);
              const meta = VALIDATION_CARD_CODES[code];
              return (
                <ValidationCard
                  key={code}
                  title={meta?.title ?? code}
                  description={meta?.description ?? code}
                  severity={check?.severity ?? "ok"}
                  count={check?.count ?? 0}
                  samples={check?.samples}
                  snapshots={check?.snapshots}
                  testId={`validation-card-${code}`}
                />
              );
            })}
          </div>

          {result.warnings.length > 0 ? (
            <JsonViewer title="предупреждения" value={result.warnings} testId="validation-warnings-list" />
          ) : null}
          {result.errors.length > 0 ? (
            <JsonViewer title="ошибки" value={result.errors} testId="validation-errors-list" />
          ) : null}
        </div>
      )}
    </section>
  );
}

function ValidationCard({
  title,
  description,
  severity,
  count,
  samples,
  snapshots,
  testId,
}: {
  title: string;
  description: string;
  severity: string;
  count: number;
  samples?: Record<string, unknown>[];
  snapshots?: Record<string, unknown>[];
  testId: string;
}) {
  return (
    <div
      className={`rounded-lg border p-3 ${validationSeverityClass(severity)}`}
      data-testid={testId}
    >
      <div className="font-medium">{title}</div>
      <p className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">{description}</p>
      <div className="mt-2 text-2xl font-semibold">{count}</div>
      <div className="mt-1 text-xs uppercase text-zinc-500">{severity}</div>
      {samples && samples.length > 0 ? (
        <JsonViewer title="samples" value={samples.slice(0, 3)} />
      ) : null}
      {snapshots && snapshots.length > 0 ? (
        <JsonViewer title="snapshots" value={snapshots} />
      ) : null}
    </div>
  );
}
