// FILE: corpsite-ui/app/admin/system/_components/user-linkage-operations/OperationsItemDetailDrawer.tsx
"use client";

import { useCallback, useEffect, useState } from "react";

import {
  fetchOperationsItem,
  mapUserLinkageOperationsApiError,
  type UserLinkageOperationsItemDetail,
} from "../../_lib/userLinkageOperationsApi.client";
import {
  formatAuditSummary,
  itemActionLabel,
  itemStatusClass,
  itemStatusLabel,
  operationLabel,
} from "../../_lib/userLinkageOperationsLabels";
import { formatDateTime } from "../../_lib/adminSystemLabels";
import ErrorBanner from "../shared/ErrorBanner";
import JsonViewer from "../shared/JsonViewer";
import OperationsSideDrawer from "./OperationsSideDrawer";

type OperationsItemDetailDrawerProps = {
  itemId: number | null;
  onClose: () => void;
  onOpenRun?: (runId: number) => void;
};

export default function OperationsItemDetailDrawer({
  itemId,
  onClose,
  onOpenRun,
}: OperationsItemDetailDrawerProps) {
  const [detail, setDetail] = useState<UserLinkageOperationsItemDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (id: number) => {
    setLoading(true);
    setError(null);
    try {
      const row = await fetchOperationsItem(id);
      setDetail(row);
    } catch (err) {
      setError(mapUserLinkageOperationsApiError(err, "Не удалось загрузить детали элемента"));
      setDetail(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (itemId === null) {
      setDetail(null);
      setError(null);
      return;
    }
    void load(itemId);
  }, [itemId, load]);

  return (
    <OperationsSideDrawer
      open={itemId !== null}
      title={`Детали элемента #${itemId ?? "…"}`}
      onClose={onClose}
      loading={loading}
      testId="operations-item-detail-drawer"
    >
      <ErrorBanner message={error} />
      {detail ? (
        <div className="space-y-4 text-sm">
          <div className="grid gap-2 sm:grid-cols-2">
            <Field label="Запуск" value={
              onOpenRun ? (
                <button
                  type="button"
                  className="text-blue-600 hover:underline dark:text-blue-400"
                  onClick={() => onOpenRun(detail.run_id)}
                >
                  #{detail.run_id} ({operationLabel(detail.run_operation ?? "")})
                </button>
              ) : (
                `#${detail.run_id}`
              )
            } />
            <Field label="Действие" value={itemActionLabel(detail.action)} />
            <Field
              label="Статус"
              value={
                <span className={`rounded px-1.5 py-0.5 text-xs ${itemStatusClass(detail.status)}`}>
                  {itemStatusLabel(detail.status)}
                </span>
              }
            />
            <Field label="Пользователь" value={detail.login ? `${detail.login} (#${detail.user_id})` : `#${detail.user_id}`} />
            <Field
              label="Сотрудник"
              value={
                detail.proposed_employee_id
                  ? `${detail.employee_name ?? "—"} (#${detail.proposed_employee_id})`
                  : "—"
              }
            />
            <Field label="Создан" value={formatDateTime(detail.created_at)} />
            <Field label="Аудит" value={formatAuditSummary(detail.audit_summary)} />
          </div>

          {detail.reason_codes.length > 0 ? (
            <div>
              <div className="text-xs font-medium text-zinc-600 dark:text-zinc-400">Коды причин</div>
              <p className="mt-1">{detail.reason_codes.join(", ")}</p>
            </div>
          ) : null}

          <JsonViewer title="Снимок до" value={detail.before_user_snapshot} testId="item-before-snapshot" />
          <JsonViewer title="Снимок после" value={detail.after_user_snapshot} testId="item-after-snapshot" />
          <JsonViewer title="Данные отката" value={detail.rollback_payload} testId="item-rollback-payload" />
          <JsonViewer title="Сводка запуска" value={detail.run_summary} />
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
