// FILE: corpsite-ui/app/admin/system/_components/personnel-lifecycle/LifecycleRunsTable.tsx
"use client";

import { useCallback, useEffect, useState } from "react";

import {
  fetchLifecycleRun,
  fetchLifecycleRuns,
  mapPersonnelLifecycleApiError,
  type LifecycleRunDetail,
  type LifecycleRunSummary,
} from "../../_lib/personnelLifecycleApi.client";
import {
  formatDurationBetween,
  lifecycleStatusClass,
} from "../../_lib/personnelLifecycleLabels";
import { formatActorLabel, formatDateTime } from "../../_lib/adminSystemLabels";
import ErrorBanner from "../shared/ErrorBanner";
import JsonViewer from "../shared/JsonViewer";

const PAGE_SIZE = 50;

type LifecycleRunsTableProps = {
  refreshToken?: number;
};

export default function LifecycleRunsTable({ refreshToken = 0 }: LifecycleRunsTableProps) {
  const [items, setItems] = useState<LifecycleRunSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [detail, setDetail] = useState<LifecycleRunDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchLifecycleRuns({
        limit: PAGE_SIZE,
        offset,
        sort_by: "started_at",
        sort_dir: "desc",
      });
      setItems(res.items);
      setTotal(res.total);
    } catch (err) {
      setError(mapPersonnelLifecycleApiError(err, "Не удалось загрузить lifecycle runs"));
    } finally {
      setLoading(false);
    }
  }, [offset]);

  useEffect(() => {
    void load();
  }, [load, refreshToken]);

  async function openDetail(runId: number): Promise<void> {
    setDetailLoading(true);
    setError(null);
    try {
      const row = await fetchLifecycleRun(runId);
      setDetail(row);
    } catch (err) {
      setError(mapPersonnelLifecycleApiError(err, "Не удалось загрузить детали run"));
    } finally {
      setDetailLoading(false);
    }
  }

  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <section className="space-y-4" data-testid="lifecycle-runs-table">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">Запуски цикла</h2>
        <button
          type="button"
          onClick={() => void load()}
          disabled={loading}
          className="rounded-lg border border-zinc-300 px-3 py-1 text-sm dark:border-zinc-600"
          data-testid="lifecycle-runs-refresh"
        >
          Обновить
        </button>
      </div>

      <ErrorBanner message={error} />

      {loading ? (
        <p className="text-sm text-zinc-500" data-testid="lifecycle-runs-loading">
          Загрузка…
        </p>
      ) : items.length === 0 ? (
        <p className="text-sm text-zinc-500" data-testid="lifecycle-runs-empty">
          Нет запусков цикла.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm" data-testid="lifecycle-runs-table-grid">
            <thead>
              <tr className="border-b border-zinc-200 text-left dark:border-zinc-700">
                {[
                  "run_id",
                  "previous_snapshot_id",
                  "snapshot_id",
                  "status",
                  "started_at",
                  "completed_at",
                  "duration",
                  "actor",
                  "events_created",
                  "persons_created",
                  "assignments_created",
                  "warnings",
                  "errors",
                  "",
                ].map((h) => (
                  <th key={h || "actions"} className="px-2 py-2 font-medium text-zinc-600 dark:text-zinc-400">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr
                  key={row.run_id}
                  className="border-b border-zinc-100 dark:border-zinc-800"
                  data-testid={`lifecycle-run-row-${row.run_id}`}
                >
                  <td className="px-2 py-2">{row.run_id}</td>
                  <td className="px-2 py-2">{row.previous_snapshot_id}</td>
                  <td className="px-2 py-2">{row.snapshot_id}</td>
                  <td className="px-2 py-2">
                    <span className={`rounded px-1.5 py-0.5 text-xs ${lifecycleStatusClass(row.status)}`}>
                      {row.status}
                    </span>
                  </td>
                  <td className="px-2 py-2">{formatDateTime(row.started_at)}</td>
                  <td className="px-2 py-2">{formatDateTime(row.completed_at)}</td>
                  <td className="px-2 py-2">{formatDurationBetween(row.started_at, row.completed_at)}</td>
                  <td className="px-2 py-2">{formatActorLabel(row.actor_user_id)}</td>
                  <td className="px-2 py-2">{row.events_created}</td>
                  <td className="px-2 py-2">{row.persons_created}</td>
                  <td className="px-2 py-2">{row.assignments_created}</td>
                  <td className="px-2 py-2">{row.warnings_count}</td>
                  <td className="px-2 py-2">{row.errors_count}</td>
                  <td className="px-2 py-2">
                    <button
                      type="button"
                      className="text-blue-600 hover:underline dark:text-blue-400"
                      onClick={() => void openDetail(row.run_id)}
                    >
                      Подробнее
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex items-center justify-between text-sm text-zinc-600 dark:text-zinc-400">
        <span>
          {total} записей · стр. {page} / {totalPages}
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={offset <= 0 || loading}
            onClick={() => setOffset((v) => Math.max(0, v - PAGE_SIZE))}
            className="rounded border px-2 py-1 disabled:opacity-50 dark:border-zinc-600"
          >
            ←
          </button>
          <button
            type="button"
            disabled={offset + PAGE_SIZE >= total || loading}
            onClick={() => setOffset((v) => v + PAGE_SIZE)}
            className="rounded border px-2 py-1 disabled:opacity-50 dark:border-zinc-600"
          >
            →
          </button>
        </div>
      </div>

      {detail || detailLoading ? (
        <div
          className="fixed inset-0 z-50 flex justify-end bg-black/30"
          role="dialog"
          aria-modal="true"
          data-testid="lifecycle-run-detail-drawer"
        >
          <div className="h-full w-full max-w-lg overflow-y-auto border-l border-zinc-200 bg-white p-4 dark:border-zinc-700 dark:bg-zinc-950">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-semibold">
                Запуск #{detail?.run_id ?? "…"}
              </h3>
              <button
                type="button"
                onClick={() => setDetail(null)}
                className="rounded border px-2 py-1 text-sm dark:border-zinc-600"
              >
                Закрыть
              </button>
            </div>
            {detailLoading ? (
              <p className="text-sm text-zinc-500">Загрузка…</p>
            ) : detail ? (
              <div className="space-y-3 text-sm">
                <p>
                  Статус:{" "}
                  <span className={`rounded px-1.5 py-0.5 text-xs ${lifecycleStatusClass(detail.status)}`}>
                    {detail.status}
                  </span>
                </p>
                <p>Начало: {formatDateTime(detail.started_at)}</p>
                <p>Завершение: {formatDateTime(detail.completed_at)}</p>
                <JsonViewer title="summary" value={detail.summary} />
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
    </section>
  );
}
