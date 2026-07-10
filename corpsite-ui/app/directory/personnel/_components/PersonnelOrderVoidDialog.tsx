"use client";

import * as React from "react";

import {
  mapPersonnelOrdersApiError,
  voidPersonnelOrder,
  type PersonnelOrderDetailResponse,
} from "../_lib/personnelOrdersApi.client";

type Props = {
  open: boolean;
  orderId: number;
  onClose: () => void;
  onVoided: (detail: PersonnelOrderDetailResponse) => void;
};

export default function PersonnelOrderVoidDialog({ open, orderId, onClose, onVoided }: Props) {
  const [reason, setReason] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!open) return;
    setReason("");
    setError(null);
    setSubmitting(false);
  }, [open]);

  if (!open) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = reason.trim();
    if (!trimmed) {
      setError("Укажите причину аннулирования.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const detail = await voidPersonnelOrder(orderId, trimmed);
      onVoided(detail);
      onClose();
    } catch (err) {
      setError(mapPersonnelOrdersApiError(err, "Не удалось аннулировать приказ."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4" data-testid="personnel-order-void-dialog">
      <button type="button" aria-label="Закрыть" className="absolute inset-0 bg-black/40" onClick={onClose} />
      <form
        onSubmit={handleSubmit}
        className="relative w-full max-w-md rounded-xl border border-zinc-200 bg-white p-5 shadow-xl dark:border-zinc-800 dark:bg-zinc-950"
      >
        <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Аннулировать приказ</h3>
        <p className="mt-1 text-sm text-zinc-500">Действие необратимо для статуса приказа. Укажите причину.</p>
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={4}
          className="mt-3 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          placeholder="Причина аннулирования"
          required
        />
        {error ? (
          <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900/55 dark:bg-red-950/35 dark:text-red-200">
            {error}
          </div>
        ) : null}
        <div className="mt-4 flex justify-end gap-2">
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
            className="rounded-lg bg-red-700 px-3 py-2 text-sm font-medium text-white disabled:opacity-60"
          >
            {submitting ? "…" : "Аннулировать"}
          </button>
        </div>
      </form>
    </div>
  );
}
