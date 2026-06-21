// FILE: corpsite-ui/app/admin/system/_components/user-linkage-operations/OperationsRunDetailDrawer.tsx
"use client";

import { useCallback, useEffect, useState } from "react";

import {
  fetchOperationsRun,
  mapUserLinkageOperationsApiError,
  type UserLinkageOperationsRunDetail,
} from "../../_lib/userLinkageOperationsApi.client";
import {
  formatAuditSummary,
  itemStatusClass,
  operationLabel,
  runStatusClass,
} from "../../_lib/userLinkageOperationsLabels";
import { formatActorLabel, formatDateTime } from "../../_lib/adminSystemLabels";
import ErrorBanner from "../shared/ErrorBanner";
import JsonViewer from "../shared/JsonViewer";
import OperationsSideDrawer from "./OperationsSideDrawer";

type OperationsRunDetailDrawerProps = {
  runId: number | null;
  onClose: () => void;
  onOpenItem?: (itemId: number) => void;
};

export default function OperationsRunDetailDrawer({
  runId,
  onClose,
  onOpenItem,
}: OperationsRunDetailDrawerProps) {
  const [detail, setDetail] = useState<UserLinkageOperationsRunDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (id: number) => {
    setLoading(true);
    setError(null);
    try {
      const row = await fetchOperationsRun(id);
      setDetail(row);
    } catch (err) {
      setError(mapUserLinkageOperationsApiError(err, "Не удалось загрузить детали run"));
      setDetail(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (runId === null) {
      setDetail(null);
      setError(null);
      return;
    }
    void load(runId);
  }, [runId, load]);

  return (
    <OperationsSideDrawer
      open={runId !== null}
      title={`Run #${runId ?? "…"}`}
      onClose={onClose}
      loading={loading}
      testId="operations-run-detail-drawer"
    >
      <ErrorBanner message={error} />
      {detail ? (
        <div className="space-y-4 text-sm">
          <div className="grid gap-2 sm:grid-cols-2">
            <Field label="Operation" value={operationLabel(detail.operation)} />
            <Field
              label="Status"
              value={
                <span className={`rounded px-1.5 py-0.5 text-xs ${runStatusClass(detail.status)}`}>
                  {detail.status}
                </span>
              }
            />
            <Field label="Actor" value={detail.actor_login ?? formatActorLabel(detail.actor_user_id)} />
            <Field label="Started" value={formatDateTime(detail.started_at)} />
            <Field label="Finished" value={formatDateTime(detail.finished_at)} />
            <Field label="Items" value={String(detail.item_count)} />
            <Field label="Dry run" value={detail.dry_run ? "yes" : "no"} />
            <Field label="Audit" value={formatAuditSummary(detail.audit_summary)} />
          </div>

          {(detail.source_preview_run_id || detail.source_item_id) && (
            <div className="space-y-1">
              <div className="text-xs font-medium text-zinc-600 dark:text-zinc-400">Source references</div>
              <ul className="list-inside list-disc text-sm">
                {detail.source_preview_run_id ? (
                  <li>Preview run #{detail.source_preview_run_id}</li>
                ) : null}
                {detail.source_item_id ? <li>Source item #{detail.source_item_id}</li> : null}
              </ul>
            </div>
          )}

          <div className="grid gap-3 sm:grid-cols-2">
            <JsonViewer title="Counts by status" value={detail.item_counts_by_status} />
            <JsonViewer title="Counts by action" value={detail.item_counts_by_action} />
          </div>

          <JsonViewer title="Summary" value={detail.summary} />

          <div className="space-y-2">
            <div className="text-xs font-medium text-zinc-600 dark:text-zinc-400">Recent items</div>
            {detail.recent_items.length === 0 ? (
              <p className="text-sm text-zinc-500">Нет items.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="border-b border-zinc-200 dark:border-zinc-700">
                      {["item", "user", "action", "status", ""].map((h) => (
                        <th key={h || "act"} className="px-2 py-1 text-left font-medium text-zinc-600">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {detail.recent_items.map((item) => (
                      <tr key={item.item_id} className="border-b border-zinc-100 dark:border-zinc-800">
                        <td className="px-2 py-1">#{item.item_id}</td>
                        <td className="px-2 py-1">{item.login ?? `#${item.user_id}`}</td>
                        <td className="px-2 py-1">{item.action}</td>
                        <td className="px-2 py-1">
                          <span className={`rounded px-1 py-0.5 text-xs ${itemStatusClass(item.status)}`}>
                            {item.status}
                          </span>
                        </td>
                        <td className="px-2 py-1">
                          {onOpenItem ? (
                            <button
                              type="button"
                              className="text-blue-600 hover:underline dark:text-blue-400"
                              onClick={() => onOpenItem(item.item_id)}
                            >
                              Open
                            </button>
                          ) : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      ) : null}
    </OperationsSideDrawer>
  );
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <div className="text-xs text-zinc-500">{label}</div>
      <div className="mt-0.5 font-medium">{value}</div>
    </div>
  );
}
