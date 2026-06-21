// FILE: corpsite-ui/app/admin/system/_components/user-linkage-operations/RerunExecutePanel.tsx
"use client";

import { useState } from "react";

import {
  mapUserLinkageOperationsApiError,
  postRerunExecute,
  type UserLinkageRerunExecuteResponse,
} from "../../_lib/userLinkageOperationsApi.client";
import { runStatusClass } from "../../_lib/userLinkageOperationsLabels";
import ErrorBanner from "../shared/ErrorBanner";
import JsonViewer from "../shared/JsonViewer";

type RerunExecutePanelProps = {
  onComplete?: () => void;
};

export default function RerunExecutePanel({ onComplete }: RerunExecutePanelProps) {
  const [sourcePreviewRunId, setSourcePreviewRunId] = useState("");
  const [confirmToken, setConfirmToken] = useState("");
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<UserLinkageRerunExecuteResponse | null>(null);

  async function onSubmit(e: React.FormEvent): Promise<void> {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

    const runId = Number(sourcePreviewRunId);
    if (!sourcePreviewRunId || Number.isNaN(runId) || runId < 1) {
      setError("Укажите корректный source preview run ID");
      setLoading(false);
      return;
    }
    if (confirmToken.trim().length < 8) {
      setError("Confirm token должен содержать минимум 8 символов");
      setLoading(false);
      return;
    }
    if (reason.trim().length < 10) {
      setError("Reason должен содержать минимум 10 символов");
      setLoading(false);
      return;
    }

    try {
      const res = await postRerunExecute({
        source_preview_run_id: runId,
        confirm_token: confirmToken.trim(),
        reason: reason.trim(),
      });
      setResult(res);
      onComplete?.();
    } catch (err) {
      setError(mapUserLinkageOperationsApiError(err, "Re-run execute не удался"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="space-y-4" data-testid="rerun-execute-panel">
      <div>
        <h2 className="text-lg font-semibold">Re-run Execute</h2>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Controlled re-run of R2.4 execute from an existing preview run. Требует confirm token.
        </p>
      </div>

      <div
        className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100"
        data-testid="rerun-execute-warning"
      >
        Это mutating операция. Убедитесь, что preview run завершён и confirm token актуален.
      </div>

      <form className="space-y-4" onSubmit={(e) => void onSubmit(e)}>
        <label className="flex max-w-xs flex-col gap-1 text-sm">
          <span>Source preview run ID</span>
          <input
            type="number"
            min={1}
            value={sourcePreviewRunId}
            onChange={(e) => setSourcePreviewRunId(e.target.value)}
            className="rounded border px-2 py-1 dark:border-zinc-600 dark:bg-zinc-900"
            data-testid="rerun-source-preview-run-id"
          />
        </label>

        <label className="flex max-w-lg flex-col gap-1 text-sm">
          <span>Confirm token</span>
          <input
            type="text"
            value={confirmToken}
            onChange={(e) => setConfirmToken(e.target.value)}
            className="rounded border px-2 py-1 font-mono text-sm dark:border-zinc-600 dark:bg-zinc-900"
            data-testid="rerun-confirm-token"
          />
        </label>

        <label className="flex max-w-lg flex-col gap-1 text-sm">
          <span>Reason (min 10 chars)</span>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
            className="rounded border px-2 py-1 dark:border-zinc-600 dark:bg-zinc-900"
            data-testid="rerun-reason"
          />
        </label>

        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          data-testid="rerun-submit"
        >
          {loading ? "Executing…" : "Execute re-run"}
        </button>
      </form>

      <ErrorBanner message={error} />

      {loading ? (
        <p className="text-sm text-zinc-500" data-testid="rerun-execute-loading">
          Выполнение…
        </p>
      ) : null}

      {result ? (
        <div className="space-y-4" data-testid="rerun-execute-result">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Metric label="Rerun run" value={`#${result.rerun_run_id}`} />
            <Metric label="Execute run" value={`#${result.execute_run_id}`} />
            <Metric
              label="Status"
              value={
                <span className={`rounded px-1.5 py-0.5 text-xs ${runStatusClass(result.run_status)}`}>
                  {result.run_status}
                </span>
              }
            />
            <Metric label="Linked" value={String(result.execute.applied)} />
            <Metric label="Skipped" value={String(result.execute.skipped)} />
            <Metric label="Failed" value={String(result.execute.failed)} />
          </div>
          <JsonViewer title="Execute result" value={result.execute} testId="rerun-execute-detail" />
        </div>
      ) : null}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
      <div className="text-xs text-zinc-500">{label}</div>
      <div className="mt-1 text-sm font-medium">{value}</div>
    </div>
  );
}
