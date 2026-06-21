// FILE: corpsite-ui/app/admin/system/_components/user-linkage-operations/OperationsDashboard.tsx
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  fetchOperationsItems,
  fetchOperationsRuns,
  mapUserLinkageOperationsApiError,
  type UserLinkageOperationsItemListItem,
} from "../../_lib/userLinkageOperationsApi.client";
import {
  operationLabel,
  runStatusClass,
  summaryCardClass,
} from "../../_lib/userLinkageOperationsLabels";
import { formatActorLabel, formatDateTime } from "../../_lib/adminSystemLabels";
import ErrorBanner from "../shared/ErrorBanner";

type DashboardSummary = {
  totalRuns: number;
  executeRuns: number;
  manualLinks: number;
  manualUnlinks: number;
  rollbacks: number;
  repairPreviews: number;
  failedOperations: number;
};

const EMPTY_SUMMARY: DashboardSummary = {
  totalRuns: 0,
  executeRuns: 0,
  manualLinks: 0,
  manualUnlinks: 0,
  rollbacks: 0,
  repairPreviews: 0,
  failedOperations: 0,
};

type OperationsDashboardProps = {
  refreshToken?: number;
  onOpenRun?: (runId: number) => void;
  onOpenItem?: (itemId: number) => void;
};

export default function OperationsDashboard({
  refreshToken = 0,
  onOpenRun,
  onOpenItem,
}: OperationsDashboardProps) {
  const [summary, setSummary] = useState<DashboardSummary>(EMPTY_SUMMARY);
  const [latestItems, setLatestItems] = useState<UserLinkageOperationsItemListItem[]>([]);
  const [actorByRunId, setActorByRunId] = useState<Map<number, string>>(new Map());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [
        totalRes,
        executeRes,
        manualLinkRes,
        manualUnlinkRes,
        rollbackRes,
        repairRes,
        failedRes,
        itemsRes,
        runsRes,
      ] = await Promise.all([
        fetchOperationsRuns({ limit: 1, offset: 0 }),
        fetchOperationsRuns({ operation: "USER_LINKAGE_EXECUTE", limit: 1, offset: 0 }),
        fetchOperationsRuns({ operation: "USER_LINKAGE_MANUAL_LINK", limit: 1, offset: 0 }),
        fetchOperationsRuns({ operation: "USER_LINKAGE_MANUAL_UNLINK", limit: 1, offset: 0 }),
        fetchOperationsRuns({ operation: "USER_LINKAGE_ROLLBACK_ITEM", limit: 1, offset: 0 }),
        fetchOperationsRuns({ operation: "USER_LINKAGE_REPAIR_PREVIEW", limit: 1, offset: 0 }),
        fetchOperationsRuns({ status: "failed", limit: 1, offset: 0 }),
        fetchOperationsItems({ limit: 20, offset: 0 }),
        fetchOperationsRuns({ limit: 20, offset: 0 }),
      ]);

      setSummary({
        totalRuns: totalRes.total,
        executeRuns: executeRes.total,
        manualLinks: manualLinkRes.total,
        manualUnlinks: manualUnlinkRes.total,
        rollbacks: rollbackRes.total,
        repairPreviews: repairRes.total,
        failedOperations: failedRes.total,
      });
      setLatestItems(itemsRes.items);

      const actors = new Map<number, string>();
      for (const run of runsRes.items) {
        const label = run.actor_login ?? formatActorLabel(run.actor_user_id);
        actors.set(run.run_id, label);
      }
      setActorByRunId(actors);
    } catch (err) {
      setError(mapUserLinkageOperationsApiError(err, "Не удалось загрузить сводку операций"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load, refreshToken]);

  const summaryCards = useMemo(
    () => [
      { label: "Total R2 runs", value: summary.totalRuns, kind: "info" as const },
      { label: "Execute runs", value: summary.executeRuns, kind: "success" as const },
      { label: "Manual links", value: summary.manualLinks, kind: "info" as const },
      { label: "Manual unlinks", value: summary.manualUnlinks, kind: "warn" as const },
      { label: "Rollbacks", value: summary.rollbacks, kind: "warn" as const },
      { label: "Repair previews", value: summary.repairPreviews, kind: "muted" as const },
      { label: "Failed operations", value: summary.failedOperations, kind: "danger" as const },
    ],
    [summary],
  );

  return (
    <section className="space-y-6" data-testid="operations-dashboard">
      <div>
        <h2 className="text-lg font-semibold">Operations Dashboard</h2>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Read-only visibility into R2 user linkage operations (ADR-044 R2.5g).
        </p>
      </div>

      <ErrorBanner message={error} />

      {loading ? (
        <p className="text-sm text-zinc-500" data-testid="operations-dashboard-loading">
          Загрузка…
        </p>
      ) : (
        <>
          <div
            className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"
            data-testid="operations-dashboard-summary"
          >
            {summaryCards.map((card) => (
              <div key={card.label} className={summaryCardClass(card.kind)}>
                <div className="text-xs text-zinc-600 dark:text-zinc-400">{card.label}</div>
                <div className="mt-1 text-2xl font-semibold">{card.value}</div>
              </div>
            ))}
          </div>

          <div className="space-y-3">
            <h3 className="text-base font-semibold">Latest operations</h3>
            {latestItems.length === 0 ? (
              <p className="text-sm text-zinc-500" data-testid="operations-dashboard-latest-empty">
                Операции ещё не выполнялись.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm" data-testid="operations-dashboard-latest-table">
                  <thead>
                    <tr className="border-b border-zinc-200 text-left dark:border-zinc-700">
                      {["time", "operation", "actor", "status", "affected user", "affected employee", ""].map(
                        (h) => (
                          <th
                            key={h || "actions"}
                            className="px-2 py-2 font-medium text-zinc-600 dark:text-zinc-400"
                          >
                            {h}
                          </th>
                        ),
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {latestItems.map((row) => (
                      <tr
                        key={row.item_id}
                        className="border-b border-zinc-100 dark:border-zinc-800"
                        data-testid={`operations-latest-row-${row.item_id}`}
                      >
                        <td className="px-2 py-2">{formatDateTime(row.created_at)}</td>
                        <td className="px-2 py-2">
                          {operationLabel(row.run_operation ?? row.action)}
                        </td>
                        <td className="px-2 py-2">{actorByRunId.get(row.run_id) ?? `#${row.run_id}`}</td>
                        <td className="px-2 py-2">
                          <span
                            className={`rounded px-1.5 py-0.5 text-xs ${runStatusClass(row.run_status ?? row.status)}`}
                          >
                            {row.run_status ?? row.status}
                          </span>
                        </td>
                        <td className="px-2 py-2">
                          {row.login ? `${row.login} (#${row.user_id})` : `#${row.user_id}`}
                        </td>
                        <td className="px-2 py-2">
                          {row.proposed_employee_id
                            ? `${row.employee_name ?? "—"} (#${row.proposed_employee_id})`
                            : "—"}
                        </td>
                        <td className="px-2 py-2">
                          <div className="flex gap-2">
                            {onOpenItem ? (
                              <button
                                type="button"
                                className="text-blue-600 hover:underline dark:text-blue-400"
                                onClick={() => onOpenItem(row.item_id)}
                              >
                                Item
                              </button>
                            ) : null}
                            {onOpenRun ? (
                              <button
                                type="button"
                                className="text-blue-600 hover:underline dark:text-blue-400"
                                onClick={() => onOpenRun(row.run_id)}
                              >
                                Run
                              </button>
                            ) : null}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </section>
  );
}
