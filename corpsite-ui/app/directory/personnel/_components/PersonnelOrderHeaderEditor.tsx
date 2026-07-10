"use client";

import * as React from "react";

import {
  PERSONNEL_ORDER_CREATE_TYPE_OPTIONS,
  mapPersonnelOrdersApiError,
  updatePersonnelOrder,
  type PersonnelOrderDetailResponse,
  type PersonnelOrderHeader,
} from "../_lib/personnelOrdersApi.client";

type Props = {
  order: PersonnelOrderHeader;
  disabled?: boolean;
  onSaved: (detail: PersonnelOrderDetailResponse) => void;
};

export default function PersonnelOrderHeaderEditor({ order, disabled = false, onSaved }: Props) {
  const [orderNumber, setOrderNumber] = React.useState(order.order_number || "");
  const [orderDate, setOrderDate] = React.useState(order.order_date || "");
  const [orderTypeCode, setOrderTypeCode] = React.useState(order.order_type_code);
  const [comment, setComment] = React.useState(order.comment || "");
  const [basisSummary, setBasisSummary] = React.useState(order.basis_summary || "");
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [message, setMessage] = React.useState<string | null>(null);

  React.useEffect(() => {
    setOrderNumber(order.order_number || "");
    setOrderDate(order.order_date || "");
    setOrderTypeCode(order.order_type_code);
    setComment(order.comment || "");
    setBasisSummary(order.basis_summary || "");
    setError(null);
    setMessage(null);
  }, [order]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (disabled) return;
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const payload: Record<string, string> = {
        order_type_code: orderTypeCode,
        comment,
        basis_summary: basisSummary,
      };
      if (orderNumber.trim()) payload.order_number = orderNumber.trim();
      if (orderDate.trim()) payload.order_date = orderDate.trim();

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
    <form className="space-y-3" onSubmit={handleSave} data-testid="personnel-order-header-editor">
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
            № приказа (из журнала)
          </label>
          <input
            value={orderNumber}
            onChange={(e) => setOrderNumber(e.target.value)}
            disabled={disabled}
            placeholder="Заполнить перед регистрацией"
            className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm disabled:opacity-60 dark:border-zinc-700 dark:bg-zinc-950"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
            Дата приказа
          </label>
          <input
            type="date"
            value={orderDate}
            onChange={(e) => setOrderDate(e.target.value)}
            disabled={disabled}
            className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm disabled:opacity-60 dark:border-zinc-700 dark:bg-zinc-950"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
            Тип
          </label>
          <select
            value={orderTypeCode}
            onChange={(e) => setOrderTypeCode(e.target.value)}
            disabled={disabled}
            className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm disabled:opacity-60 dark:border-zinc-700 dark:bg-zinc-950"
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
        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
            Основание
          </label>
          <input
            value={basisSummary}
            onChange={(e) => setBasisSummary(e.target.value)}
            disabled={disabled}
            className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm disabled:opacity-60 dark:border-zinc-700 dark:bg-zinc-950"
          />
        </div>
      </div>
      <div>
        <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
          Комментарий
        </label>
        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          disabled={disabled}
          rows={2}
          className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm disabled:opacity-60 dark:border-zinc-700 dark:bg-zinc-950"
        />
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
