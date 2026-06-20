// FILE: corpsite-ui/app/admin/system/_components/tabs/AssignmentsTab.tsx
"use client";

import { useCallback, useEffect, useState } from "react";

import {
  fetchAssignmentDrift,
  mapAdminSystemApiError,
  reconcileAssignment,
  type AssignmentDriftItem,
  type ReconcileResult,
} from "../../_lib/adminSystemApi.client";
import ErrorBanner, { SuccessBanner } from "../shared/ErrorBanner";
import ConfirmDialog from "../shared/ConfirmDialog";

export default function AssignmentsTab() {
  const [items, setItems] = useState<AssignmentDriftItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [preview, setPreview] = useState<ReconcileResult | null>(null);
  const [confirmEmployeeId, setConfirmEmployeeId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchAssignmentDrift({ limit: 200 });
      setItems(res.items);
      setTotal(res.total);
    } catch (err) {
      setError(mapAdminSystemApiError(err, "Не удалось загрузить drift"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleReconcile(employeeId: number, dryRun: boolean): Promise<void> {
    setError(null);
    setSuccess(null);
    try {
      const res = await reconcileAssignment(employeeId, dryRun);
      if (dryRun) {
        setPreview(res);
        setSuccess(`Dry-run для employee #${employeeId}: ${res.has_drift ? "есть drift" : "нет drift"}`);
      } else {
        setSuccess(
          res.applied
            ? `Применено для employee #${employeeId}`
            : `Не применено: ${res.reason ?? "no changes"}`,
        );
        await load();
      }
    } catch (err) {
      setError(mapAdminSystemApiError(err, "Reconcile failed"));
    }
  }

  return (
    <div className="space-y-4">
      <ErrorBanner message={error} />
      <SuccessBanner message={success} />

      <div className="flex flex-wrap items-center gap-3">
        <p className="text-sm">
          Drift rows: <strong>{total}</strong> (по умолчанию reconcile — dry_run)
        </p>
        <button type="button" onClick={() => void load()} className="rounded-lg border px-3 py-2 text-sm">
          Обновить
        </button>
      </div>

      {preview ? (
        <details open className="rounded border border-zinc-200 p-3 text-sm dark:border-zinc-700">
          <summary className="cursor-pointer font-medium">Последний dry-run preview</summary>
          <pre className="mt-2 max-h-48 overflow-auto text-xs">{JSON.stringify(preview, null, 2)}</pre>
        </details>
      ) : null}

      {loading ? (
        <p className="text-sm text-zinc-500">Загрузка…</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-700">
          <table className="min-w-full text-sm">
            <thead className="bg-zinc-50 dark:bg-zinc-900">
              <tr>
                <th className="px-3 py-2 text-left">Employee</th>
                <th className="px-3 py-2 text-left">Assignment</th>
                <th className="px-3 py-2 text-left">Diff fields</th>
                <th className="px-3 py-2 text-left">Действия</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr key={row.employee_id} className="border-t dark:border-zinc-800">
                  <td className="px-3 py-2">#{row.employee_id}</td>
                  <td className="px-3 py-2">#{row.assignment_id ?? "—"}</td>
                  <td className="px-3 py-2">
                    {row.diff && Object.keys(row.diff).length
                      ? Object.entries(row.diff).map(([field, d]) => (
                          <div key={field} className="text-xs">
                            {field}: {JSON.stringify(d?.employee)} → {JSON.stringify(d?.assignment)}
                          </div>
                        ))
                      : "—"}
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex gap-1">
                      <button
                        type="button"
                        onClick={() => void handleReconcile(row.employee_id, true)}
                        className="rounded border px-2 py-0.5 text-xs dark:border-zinc-600"
                      >
                        Проверить
                      </button>
                      <button
                        type="button"
                        onClick={() => setConfirmEmployeeId(row.employee_id)}
                        className="rounded bg-amber-600 px-2 py-0.5 text-xs text-white"
                      >
                        Применить
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ConfirmDialog
        open={confirmEmployeeId != null}
        title="Применить reconciliation?"
        message={`Синхронизировать snapshot employee #${confirmEmployeeId} с primary assignment? Это изменит данные в БД.`}
        confirmLabel="Применить (dry_run=false)"
        onCancel={() => setConfirmEmployeeId(null)}
        onConfirm={() => {
          const eid = confirmEmployeeId;
          setConfirmEmployeeId(null);
          if (eid != null) void handleReconcile(eid, false);
        }}
      />
    </div>
  );
}
