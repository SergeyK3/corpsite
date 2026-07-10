"use client";

import * as React from "react";

import {
  PERSONNEL_ORDER_CREATE_TYPE_OPTIONS,
  createPersonnelOrder,
  mapPersonnelOrdersApiError,
  type PersonnelOrderDetailResponse,
} from "../_lib/personnelOrdersApi.client";

type Props = {
  open: boolean;
  onClose: () => void;
  onCreated: (detail: PersonnelOrderDetailResponse) => void;
};

export default function PersonnelOrderCreateDialog({ open, onClose, onCreated }: Props) {
  const [orderTypeCode, setOrderTypeCode] = React.useState("HIRE");
  const [comment, setComment] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!open) return;
    setOrderTypeCode("HIRE");
    setComment("");
    setError(null);
    setSubmitting(false);
  }, [open]);

  if (!open) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const detail = await createPersonnelOrder({
        order_type_code: orderTypeCode,
        source_mode: "PAPER",
        comment: comment.trim() || null,
      });
      onCreated(detail);
      onClose();
    } catch (err) {
      setError(mapPersonnelOrdersApiError(err, "Не удалось создать приказ."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4" data-testid="personnel-order-create-dialog">
      <button type="button" aria-label="Закрыть" className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative w-full max-w-md rounded-xl border border-zinc-200 bg-white p-5 shadow-xl dark:border-zinc-800 dark:bg-zinc-950">
        <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Создать приказ</h2>
        <p className="mt-1 text-sm text-zinc-500">
          Черновик без номера и даты. Регистрационные реквизиты заполняются позже из бумажного журнала.
        </p>

        <form className="mt-4 space-y-4" onSubmit={handleSubmit}>
          <div>
            <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
              Тип приказа
            </label>
            <select
              value={orderTypeCode}
              onChange={(e) => setOrderTypeCode(e.target.value)}
              className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
              required
            >
              {PERSONNEL_ORDER_CREATE_TYPE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
              Комментарий
            </label>
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              rows={3}
              className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
              placeholder="Необязательно"
            />
          </div>

          {error ? (
            <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900/55 dark:bg-red-950/35 dark:text-red-200">
              {error}
            </div>
          ) : null}

          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700"
            >
              Отмена
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="rounded-lg bg-zinc-900 px-3 py-2 text-sm font-medium text-white disabled:opacity-60 dark:bg-zinc-100 dark:text-zinc-900"
            >
              {submitting ? "Создание…" : "Создать черновик"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
