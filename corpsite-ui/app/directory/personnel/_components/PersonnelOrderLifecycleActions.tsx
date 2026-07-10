"use client";

import * as React from "react";

import {
  applyPersonnelOrder,
  canApplyPersonnelOrderAction,
  canRegisterPersonnelOrder,
  canVoidPersonnelOrder,
  isEditablePersonnelOrderStatus,
  mapPersonnelOrdersApiError,
  markPersonnelOrderReadyForSignature,
  registerPersonnelOrder,
  type PersonnelOrderDetailResponse,
  type PersonnelOrderHeader,
} from "../_lib/personnelOrdersApi.client";
import PersonnelOrderVoidDialog from "./PersonnelOrderVoidDialog";

type Props = {
  order: PersonnelOrderHeader;
  itemCount: number;
  linkedEventCount: number;
  onChanged: (detail: PersonnelOrderDetailResponse) => void;
  onToast?: (message: string, kind?: "success" | "error") => void;
};

export default function PersonnelOrderLifecycleActions({
  order,
  itemCount,
  linkedEventCount,
  onChanged,
  onToast,
}: Props) {
  const [busy, setBusy] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [voidOpen, setVoidOpen] = React.useState(false);
  const [confirmApply, setConfirmApply] = React.useState(false);
  const [confirmRegister, setConfirmRegister] = React.useState(false);
  const applyInFlightRef = React.useRef(false);

  const hasRegistrationFields = Boolean(String(order.order_number || "").trim() && order.order_date);
  const canReady = String(order.status).toUpperCase() === "DRAFT";
  const canRegister = canRegisterPersonnelOrder(order.status);
  const canApply = canApplyPersonnelOrderAction(order.status, linkedEventCount);
  const canVoid = canVoidPersonnelOrder(order.status);
  const editable = isEditablePersonnelOrderStatus(order.status);

  React.useEffect(() => {
    if (!canApply) setConfirmApply(false);
  }, [canApply]);

  async function runAction(key: string, action: () => Promise<PersonnelOrderDetailResponse>, successMessage: string) {
    if (key === "apply") {
      if (!canApplyPersonnelOrderAction(order.status, linkedEventCount) || applyInFlightRef.current) {
        return;
      }
      applyInFlightRef.current = true;
    }
    setBusy(key);
    setError(null);
    try {
      const detail = await action();
      onChanged(detail);
      onToast?.(successMessage, "success");
    } catch (err) {
      const message = mapPersonnelOrdersApiError(err, "Операция не выполнена.");
      setError(message);
      onToast?.(message, "error");
    } finally {
      if (key === "apply") {
        applyInFlightRef.current = false;
      }
      setBusy(null);
      setConfirmApply(false);
      setConfirmRegister(false);
    }
  }

  return (
    <div className="space-y-3" data-testid="personnel-order-lifecycle-actions">
      <div className="flex flex-wrap gap-2">
        {canReady ? (
          <button
            type="button"
            disabled={busy != null || itemCount < 1 || !hasRegistrationFields}
            title={
              !hasRegistrationFields
                ? "Сначала заполните № и дату приказа"
                : itemCount < 1
                  ? "Добавьте хотя бы один пункт"
                  : undefined
            }
            onClick={() =>
              void runAction(
                "ready",
                () => markPersonnelOrderReadyForSignature(order.order_id),
                "Приказ переведён в статус «На подписи».",
              )
            }
            className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm font-medium text-amber-900 disabled:opacity-50 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-100"
          >
            {busy === "ready" ? "…" : "К подписи"}
          </button>
        ) : null}

        {canRegister ? (
          <button
            type="button"
            disabled={busy != null || itemCount < 1 || !hasRegistrationFields}
            title={
              !hasRegistrationFields
                ? "Сначала заполните № и дату приказа"
                : itemCount < 1
                  ? "Добавьте хотя бы один пункт"
                  : undefined
            }
            onClick={() => setConfirmRegister(true)}
            className="rounded-lg border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm font-medium text-emerald-900 disabled:opacity-50 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-100"
          >
            Зарегистрировать
          </button>
        ) : null}

        {canApply ? (
          <button
            type="button"
            data-testid="personnel-order-apply-button"
            disabled={busy != null}
            onClick={() => setConfirmApply(true)}
            className="rounded-lg bg-zinc-900 px-3 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
          >
            Применить
          </button>
        ) : null}

        {canVoid ? (
          <button
            type="button"
            disabled={busy != null}
            onClick={() => setVoidOpen(true)}
            className="rounded-lg border border-red-300 bg-red-50 px-3 py-2 text-sm font-medium text-red-800 disabled:opacity-50 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200"
          >
            Аннулировать
          </button>
        ) : null}
      </div>

      {editable && !hasRegistrationFields ? (
        <p className="text-xs text-amber-800 dark:text-amber-200">
          Для регистрации заполните номер и дату приказа из бумажного журнала.
        </p>
      ) : null}

      {error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900/55 dark:bg-red-950/35 dark:text-red-200">
          {error}
        </div>
      ) : null}

      {confirmRegister ? (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm dark:border-emerald-900/50 dark:bg-emerald-950/30">
          <p className="text-emerald-950 dark:text-emerald-100">
            Зарегистрировать приказ {order.order_number ? `№${order.order_number}` : ""} как REGISTERED?
          </p>
          <div className="mt-2 flex gap-2">
            <button
              type="button"
              disabled={busy != null}
              onClick={() =>
                void runAction(
                  "register",
                  () => registerPersonnelOrder(order.order_id, "REGISTERED"),
                  "Приказ зарегистрирован.",
                )
              }
              className="rounded-lg bg-emerald-700 px-3 py-1.5 text-sm text-white disabled:opacity-60"
            >
              {busy === "register" ? "…" : "Подтвердить"}
            </button>
            <button
              type="button"
              onClick={() => setConfirmRegister(false)}
              className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700"
            >
              Отмена
            </button>
          </div>
        </div>
      ) : null}

      {confirmApply && canApply ? (
        <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-3 text-sm dark:border-zinc-800 dark:bg-zinc-900/40">
          <p>Применить приказ и создать кадровые события сотрудников?</p>
          <div className="mt-2 flex gap-2">
            <button
              type="button"
              data-testid="personnel-order-apply-confirm"
              disabled={busy != null}
              onClick={() =>
                void runAction(
                  "apply",
                  () => applyPersonnelOrder(order.order_id),
                  "Приказ применён.",
                )
              }
              className="rounded-lg bg-zinc-900 px-3 py-1.5 text-sm text-white disabled:opacity-60 dark:bg-zinc-100 dark:text-zinc-900"
            >
              {busy === "apply" ? "…" : "Подтвердить"}
            </button>
            <button
              type="button"
              onClick={() => setConfirmApply(false)}
              className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700"
            >
              Отмена
            </button>
          </div>
        </div>
      ) : null}

      <PersonnelOrderVoidDialog
        open={voidOpen}
        orderId={order.order_id}
        onClose={() => setVoidOpen(false)}
        onVoided={(detail) => {
          onChanged(detail);
          onToast?.("Приказ аннулирован.", "success");
        }}
      />
    </div>
  );
}
