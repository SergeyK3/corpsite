"use client";

import * as React from "react";

import {
  PERSONNEL_ORDER_CREATE_TYPE_OPTIONS,
  getPersonnelOrderSignatoryDefault,
  mapPersonnelOrdersApiError,
  updatePersonnelOrder,
  type PersonnelOrderDetailResponse,
  type PersonnelOrderHeader,
  type PersonnelOrderUpdatePayload,
} from "../_lib/personnelOrdersApi.client";
import type { PersonnelOrderRequisitesSnapshot } from "../_lib/personnelOrderDocumentRequisites";
import { personnelOrderTypeLabel } from "../_lib/personnelOrderLabels";
import PersonnelOrderTypeBadge from "./PersonnelOrderTypeBadge";

const FIELD_LABEL_CLASS = "mb-1 block text-sm font-medium text-zinc-800 dark:text-zinc-200";
const FIELD_INPUT_CLASS =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm disabled:opacity-60 dark:border-zinc-700 dark:bg-zinc-950";

function isSignatoryComplete(
  order: Pick<PersonnelOrderHeader, "signed_by_name" | "signed_by_position">,
) {
  return Boolean((order.signed_by_name || "").trim() && (order.signed_by_position || "").trim());
}

function snapshotFromFields(
  orderDate: string,
  signedByName: string,
  signedByPosition: string,
): PersonnelOrderRequisitesSnapshot {
  return {
    order_date: orderDate.trim() || null,
    signed_by_name: signedByName.trim() || null,
    signed_by_position: signedByPosition.trim() || null,
  };
}

type Props = {
  order: PersonnelOrderHeader;
  disabled?: boolean;
  onSaved: (detail: PersonnelOrderDetailResponse) => void;
  /** Live requisites from header inputs — for in-drawer preview before/without save. */
  onRequisitesChange?: (snapshot: PersonnelOrderRequisitesSnapshot) => void;
};

export default function PersonnelOrderHeaderEditor({
  order,
  disabled = false,
  onSaved,
  onRequisitesChange,
}: Props) {
  const [orderNumber, setOrderNumber] = React.useState(order.order_number || "");
  const [orderDate, setOrderDate] = React.useState(order.order_date || "");
  const [signedByName, setSignedByName] = React.useState(order.signed_by_name || "");
  const [signedByPosition, setSignedByPosition] = React.useState(order.signed_by_position || "");
  const [orderTypeCode, setOrderTypeCode] = React.useState(order.order_type_code);
  const [comment, setComment] = React.useState(order.comment || "");
  const [basisSummary, setBasisSummary] = React.useState(order.basis_summary || "");
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [message, setMessage] = React.useState<string | null>(null);
  const [signatoryHint, setSignatoryHint] = React.useState<string | null>(null);
  const [prefillDone, setPrefillDone] = React.useState(false);

  React.useEffect(() => {
    setOrderNumber(order.order_number || "");
    setOrderDate(order.order_date || "");
    setSignedByName(order.signed_by_name || "");
    setSignedByPosition(order.signed_by_position || "");
    setOrderTypeCode(order.order_type_code);
    setComment(order.comment || "");
    setBasisSummary(order.basis_summary || "");
    setError(null);
    setMessage(null);
    setSignatoryHint(null);
    setPrefillDone(isSignatoryComplete(order));
  }, [order]);

  React.useEffect(() => {
    onRequisitesChange?.(snapshotFromFields(orderDate, signedByName, signedByPosition));
  }, [orderDate, signedByName, signedByPosition, onRequisitesChange]);

  React.useEffect(() => {
    if (disabled || prefillDone || isSignatoryComplete(order)) return;

    let cancelled = false;
    void (async () => {
      try {
        const defaults = await getPersonnelOrderSignatoryDefault();
        if (cancelled) return;

        const nextName =
          !(order.signed_by_name || "").trim() && defaults.signed_by_name
            ? String(defaults.signed_by_name).trim()
            : String(order.signed_by_name || signedByName || "").trim();
        const nextPosition =
          !(order.signed_by_position || "").trim() && defaults.signed_by_position
            ? String(defaults.signed_by_position).trim()
            : String(order.signed_by_position || signedByPosition || "").trim();

        if (!(order.signed_by_name || "").trim() && nextName) setSignedByName(nextName);
        if (!(order.signed_by_position || "").trim() && nextPosition) setSignedByPosition(nextPosition);
        if (defaults.warning) setSignatoryHint(defaults.warning);

        const shouldPersist =
          !isSignatoryComplete(order) && Boolean(nextName || nextPosition);
        if (shouldPersist) {
          const detail = await updatePersonnelOrder(order.order_id, {
            signed_by_name: nextName || null,
            signed_by_position: nextPosition || null,
          });
          if (!cancelled) {
            onSaved(detail);
            setMessage("Реквизиты подписанта сохранены.");
          }
        }

        if (!cancelled) setPrefillDone(true);
      } catch {
        if (!cancelled) {
          setSignatoryHint(
            "Действующий директор не найден. Заполните должность и ФИО подписанта вручную.",
          );
          setPrefillDone(true);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [disabled, onSaved, order, prefillDone]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (disabled) return;
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const payload: PersonnelOrderUpdatePayload = {
        order_type_code: orderTypeCode,
        comment,
        basis_summary: basisSummary,
      };
      if (orderNumber.trim()) payload.order_number = orderNumber.trim();
      if (orderDate.trim()) payload.order_date = orderDate.trim();

      const nextName = signedByName.trim();
      const nextPosition = signedByPosition.trim();
      const hadSavedName = Boolean((order.signed_by_name || "").trim());
      const hadSavedPosition = Boolean((order.signed_by_position || "").trim());
      if (nextName || nextPosition || hadSavedName || hadSavedPosition) {
        payload.signed_by_name = nextName;
        payload.signed_by_position = nextPosition;
      }

      const detail = await updatePersonnelOrder(order.order_id, payload);
      onSaved(detail);
      setMessage("Сохранено.");
    } catch (err) {
      setError(mapPersonnelOrdersApiError(err, "Не удалось сохранить заголовок."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="space-y-4" onSubmit={handleSave} data-testid="personnel-order-header-editor">
      <div
        className="space-y-3 rounded-xl border border-zinc-200 bg-zinc-50/80 p-3 dark:border-zinc-800 dark:bg-zinc-900/30"
        data-testid="personnel-order-type-block"
      >
        <div>
          <div className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Тип приказа</div>
          <p className="mt-1 text-xs text-zinc-500">
            Классификация приказа в журнале. Тип пункта задаётся отдельно для каждой строки ниже.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <PersonnelOrderTypeBadge typeCode={orderTypeCode} />
          <span className="text-sm text-zinc-600 dark:text-zinc-400">
            {personnelOrderTypeLabel(orderTypeCode)}
          </span>
        </div>
        <div>
          <label className={FIELD_LABEL_CLASS}>Изменить тип приказа</label>
          <select
            value={orderTypeCode}
            onChange={(e) => setOrderTypeCode(e.target.value)}
            disabled={disabled}
            data-testid="personnel-order-type-select"
            className={FIELD_INPUT_CLASS}
          >
            {PERSONNEL_ORDER_CREATE_TYPE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
            {orderTypeCode === "COMPOSITE" ? (
              <option value="COMPOSITE">Составной</option>
            ) : null}
          </select>
        </div>
      </div>

      <div className="space-y-3">
        <div className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Реквизиты</div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className={FIELD_LABEL_CLASS}>№ приказа (из журнала)</label>
            <input
              value={orderNumber}
              onChange={(e) => setOrderNumber(e.target.value)}
              disabled={disabled}
              placeholder="Заполнить перед регистрацией"
              className={FIELD_INPUT_CLASS}
            />
          </div>
          <div>
            <label className={FIELD_LABEL_CLASS}>Дата приказа</label>
            <input
              type="date"
              value={orderDate}
              onChange={(e) => setOrderDate(e.target.value)}
              disabled={disabled}
              className={FIELD_INPUT_CLASS}
              data-testid="personnel-order-header-order-date"
            />
          </div>
          <div>
            <label className={FIELD_LABEL_CLASS}>Должность подписанта</label>
            <input
              value={signedByPosition}
              onChange={(e) => setSignedByPosition(e.target.value)}
              disabled={disabled}
              placeholder="Например: Директор"
              className={FIELD_INPUT_CLASS}
              data-testid="personnel-order-header-signatory-position"
            />
          </div>
          <div>
            <label className={FIELD_LABEL_CLASS}>ФИО подписанта</label>
            <input
              value={signedByName}
              onChange={(e) => setSignedByName(e.target.value)}
              disabled={disabled}
              placeholder="Например: М. Тулеутаев"
              className={FIELD_INPUT_CLASS}
              data-testid="personnel-order-header-signatory-name"
            />
          </div>
          {signatoryHint ? (
            <div
              className="sm:col-span-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-100"
              data-testid="personnel-order-header-signatory-hint"
            >
              {signatoryHint}
            </div>
          ) : null}
          <div className="sm:col-span-2">
            <label className={FIELD_LABEL_CLASS}>Основание</label>
            <input
              value={basisSummary}
              onChange={(e) => setBasisSummary(e.target.value)}
              disabled={disabled}
              className={FIELD_INPUT_CLASS}
            />
          </div>
        </div>
        <div>
          <label className={FIELD_LABEL_CLASS}>Комментарий</label>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            disabled={disabled}
            rows={2}
            className={FIELD_INPUT_CLASS}
          />
        </div>
      </div>

      {error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900/55 dark:bg-red-950/35 dark:text-red-200">
          {error}
        </div>
      ) : null}
      {message ? <div className="text-sm text-emerald-700 dark:text-emerald-300">{message}</div> : null}

      {!disabled ? (
        <button
          type="submit"
          disabled={saving}
          className="rounded-lg border border-zinc-300 px-3 py-2 text-sm font-medium disabled:opacity-60 dark:border-zinc-700"
        >
          {saving ? "Сохранение…" : "Сохранить заголовок"}
        </button>
      ) : null}
    </form>
  );
}
