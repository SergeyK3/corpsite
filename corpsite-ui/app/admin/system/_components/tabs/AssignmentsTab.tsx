// FILE: corpsite-ui/app/admin/system/_components/tabs/AssignmentsTab.tsx
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  fetchAssignmentDrift,
  mapAdminSystemApiError,
  reconcileAssignmentsBulk,
  type AssignmentDriftItem,
  type ReconcileResult,
} from "../../_lib/adminSystemApi.client";
import ErrorBanner, { SuccessBanner } from "../shared/ErrorBanner";
import ConfirmDialog from "../shared/ConfirmDialog";
import FieldDiffList from "../shared/FieldDiffList";

type AppliedSnapshot = {
  employee_id: number;
  assignment_id?: number | null;
  diff: Record<string, { employee?: unknown; assignment?: unknown }>;
};

type BulkConfirm = {
  mode: "selected" | "all";
  dryRun: boolean;
};

export default function AssignmentsTab() {
  const [items, setItems] = useState<AssignmentDriftItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [rowPreviews, setRowPreviews] = useState<Record<number, ReconcileResult>>({});
  const [appliedSnapshots, setAppliedSnapshots] = useState<AppliedSnapshot[]>([]);
  const [bulkConfirm, setBulkConfirm] = useState<BulkConfirm | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchAssignmentDrift({ limit: 200 });
      setItems(res.items);
      setTotal(res.total);
      setSelected(new Set());
    } catch (err) {
      setError(mapAdminSystemApiError(err, "Не удалось загрузить drift"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const pageIds = useMemo(() => items.map((row) => row.employee_id), [items]);
  const allPageSelected =
    pageIds.length > 0 && pageIds.every((id) => selected.has(id));

  function toggleRow(employeeId: number): void {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(employeeId)) next.delete(employeeId);
      else next.add(employeeId);
      return next;
    });
  }

  function toggleAllPage(): void {
    if (allPageSelected) {
      setSelected(new Set());
    } else {
      setSelected(new Set(pageIds));
    }
  }

  async function runBulk(params: {
    employee_ids?: number[];
    all_drift?: boolean;
    dry_run: boolean;
  }): Promise<void> {
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      const res = await reconcileAssignmentsBulk({
        employee_ids: params.employee_ids,
        all_drift: params.all_drift,
        dry_run: params.dry_run,
      });

      if (params.dry_run) {
        const previews: Record<number, ReconcileResult> = {};
        for (const row of res.results) {
          previews[row.employee_id] = row;
        }
        setRowPreviews((prev) => ({ ...prev, ...previews }));
        setSuccess(
          `Dry-run: проверено ${res.processed}, с drift ${res.with_drift}`,
        );
      } else {
        const snapshots: AppliedSnapshot[] = [];
        for (const row of res.results) {
          if (row.applied && row.previous_diff) {
            snapshots.push({
              employee_id: row.employee_id,
              assignment_id: row.assignment_id,
              diff: row.previous_diff as Record<
                string,
                { employee?: unknown; assignment?: unknown }
              >,
            });
          }
        }
        if (snapshots.length) {
          setAppliedSnapshots((prev) => [...snapshots, ...prev].slice(0, 50));
        }
        setSuccess(`Применено: ${res.applied_count} из ${res.processed}`);
        await load();
      }
    } catch (err) {
      setError(mapAdminSystemApiError(err, "Reconcile failed"));
    } finally {
      setBusy(false);
      setBulkConfirm(null);
    }
  }

  function requestBulk(mode: "selected" | "all", dryRun: boolean): void {
    if (!dryRun) {
      setBulkConfirm({ mode, dryRun });
      return;
    }
    if (mode === "all") {
      void runBulk({ all_drift: true, dry_run: true });
    } else {
      const ids = Array.from(selected);
      if (!ids.length) {
        setError("Выберите строки для проверки");
        return;
      }
      void runBulk({ employee_ids: ids, dry_run: true });
    }
  }

  const confirmStats = useMemo(() => {
    if (!bulkConfirm || bulkConfirm.dryRun) return null;
    const ids =
      bulkConfirm.mode === "all"
        ? items.map((i) => i.employee_id)
        : Array.from(selected);
    const assignmentIds = new Set<number>();
    let changeCount = 0;
    for (const id of ids) {
      const preview = rowPreviews[id];
      const item = items.find((r) => r.employee_id === id);
      const diff = preview?.diff ?? item?.diff;
      if (item?.assignment_id) assignmentIds.add(item.assignment_id);
      changeCount += Object.keys(diff ?? {}).length;
    }
    return {
      employees: ids.length,
      assignments: assignmentIds.size || ids.length,
      changes: changeCount,
    };
  }, [bulkConfirm, items, selected, rowPreviews]);

  return (
    <div className="space-y-4">
      <ErrorBanner message={error} />
      <SuccessBanner message={success} />

      <div className="flex flex-wrap items-center gap-2">
        <p className="text-sm">
          Drift rows: <strong>{total}</strong>
        </p>
        <button
          type="button"
          onClick={() => void load()}
          disabled={busy}
          className="rounded-lg border px-3 py-2 text-sm"
        >
          Обновить
        </button>
        <button
          type="button"
          disabled={busy || selected.size === 0}
          onClick={() => requestBulk("selected", true)}
          className="rounded-lg border px-3 py-2 text-sm disabled:opacity-50"
        >
          Проверить выбранные ({selected.size})
        </button>
        <button
          type="button"
          disabled={busy || selected.size === 0}
          onClick={() => requestBulk("selected", false)}
          className="rounded-lg bg-amber-600 px-3 py-2 text-sm text-white disabled:opacity-50"
        >
          Применить выбранные
        </button>
        <button
          type="button"
          disabled={busy || total === 0}
          onClick={() => requestBulk("all", true)}
          className="rounded-lg border px-3 py-2 text-sm disabled:opacity-50"
        >
          Проверить все drift
        </button>
        <button
          type="button"
          disabled={busy || total === 0}
          onClick={() => requestBulk("all", false)}
          className="rounded-lg bg-amber-700 px-3 py-2 text-sm text-white disabled:opacity-50"
        >
          Применить все drift
        </button>
      </div>

      {appliedSnapshots.length ? (
        <section className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 dark:border-emerald-900 dark:bg-emerald-950/30">
          <h3 className="font-medium text-emerald-900 dark:text-emerald-200">
            Недавно применённые изменения
          </h3>
          <div className="mt-3 space-y-3">
            {appliedSnapshots.slice(0, 10).map((snap) => (
              <div key={`${snap.employee_id}-${snap.assignment_id}`} className="text-sm">
                <div className="font-medium">
                  Employee #{snap.employee_id}
                  {snap.assignment_id ? ` · Assignment #${snap.assignment_id}` : ""}
                </div>
                <FieldDiffList diff={snap.diff} />
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {loading ? (
        <p className="text-sm text-zinc-500">Загрузка…</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-700">
          <table className="min-w-full text-sm">
            <thead className="bg-zinc-50 dark:bg-zinc-900">
              <tr>
                <th className="px-3 py-2 text-left">
                  <input
                    type="checkbox"
                    checked={allPageSelected}
                    onChange={toggleAllPage}
                    aria-label="Выбрать все на странице"
                  />
                </th>
                <th className="px-3 py-2 text-left">Employee</th>
                <th className="px-3 py-2 text-left">Assignment</th>
                <th className="px-3 py-2 text-left">Изменения</th>
                <th className="px-3 py-2 text-left">Preview</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => {
                const preview = rowPreviews[row.employee_id];
                const displayDiff = preview?.diff ?? row.diff;
                return (
                  <tr key={row.employee_id} className="border-t dark:border-zinc-800">
                    <td className="px-3 py-2">
                      <input
                        type="checkbox"
                        checked={selected.has(row.employee_id)}
                        onChange={() => toggleRow(row.employee_id)}
                        aria-label={`Выбрать employee ${row.employee_id}`}
                      />
                    </td>
                    <td className="px-3 py-2">#{row.employee_id}</td>
                    <td className="px-3 py-2">#{row.assignment_id ?? "—"}</td>
                    <td className="px-3 py-2">
                      <FieldDiffList diff={row.diff} />
                    </td>
                    <td className="px-3 py-2">
                      {preview ? (
                        <div className="rounded border border-blue-200 bg-blue-50 p-2 dark:border-blue-900 dark:bg-blue-950/40">
                          <div className="text-xs font-medium text-blue-900 dark:text-blue-200">
                            Dry-run preview
                          </div>
                          <FieldDiffList diff={displayDiff as Record<string, { employee?: unknown; assignment?: unknown }>} />
                        </div>
                      ) : (
                        <span className="text-xs text-zinc-500">—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <ConfirmDialog
        open={bulkConfirm != null && !bulkConfirm.dryRun}
        title="Применить reconciliation?"
        message="Синхронизировать snapshot employees с primary assignments? Это изменит данные в БД."
        details={
          confirmStats ? (
            <ul className="list-disc space-y-1 pl-5 text-zinc-700 dark:text-zinc-300">
              <li>Сотрудников: {confirmStats.employees}</li>
              <li>Назначений: {confirmStats.assignments}</li>
              <li>Полей с изменениями: {confirmStats.changes}</li>
            </ul>
          ) : null
        }
        confirmLabel="Применить"
        onCancel={() => setBulkConfirm(null)}
        onConfirm={() => {
          if (!bulkConfirm) return;
          if (bulkConfirm.mode === "all") {
            void runBulk({ all_drift: true, dry_run: false });
          } else {
            void runBulk({ employee_ids: Array.from(selected), dry_run: false });
          }
        }}
      />
    </div>
  );
}
