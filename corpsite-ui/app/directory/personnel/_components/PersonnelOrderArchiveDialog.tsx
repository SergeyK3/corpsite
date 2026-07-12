"use client";

import * as React from "react";

import {
  mapPersonnelOrdersApiError,
  archivePersonnelOrder,
  type PersonnelOrderDetailResponse,
} from "../_lib/personnelOrdersApi.client";

type Props = {
  open: boolean;
  orderId: number;
  onClose: () => void;
  onArchived: (detail: PersonnelOrderDetailResponse) => void;
};

const REASON_OPTIONS = [
  { value: "completed", label: "Жизненный цикл завершён" },
  { value: "voided_record", label: "Аннулированная запись" },
  { value: "migrated_legacy", label: "Мигрировано из legacy" },
  { value: "duplicate_reference", label: "Дублирующая ссылка" },
  { value: "other", label: "Другое" },
] as const;

export default function PersonnelOrderArchiveDialog({ open, orderId, onClose, onArchived }: Props) {
  const [reasonCode, setReasonCode] = React.useState<(typeof REASON_OPTIONS)[number]["value"]>("completed");
  const [reasonText, setReasonText] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!open) return;
    setReasonCode("completed");
    setReasonText("");
    setError(null);
    setSubmitting(false);
  }, [open]);

  if (!open) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = reasonText.trim();
    if (reasonCode === "other" && !trimmed) {
      setError("Укажите текст причины для варианта «Другое».");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const detail = await archivePersonnelOrder(orderId, {
        reason_code: reasonCode,
        reason_text: trimmed || undefined,
      });
      onArchived(detail);
      onClose();
    } catch (err) {
      setError(mapPersonnelOrdersApiError(err, "Не удалось архивировать приказ."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4" data-testid="personnel-order-archive-dialog">
      <button type="button" aria-label="Закрыть" className="absolute inset-0 bg-black/40" onClick={onClose} />
      <form
        onSubmit={handleSubmit}
        className="relative w-full max-w-md rounded-xl border border-zinc-200 bg-white p-5 shadow-xl dark:border-zinc-800 dark:bg-zinc-950"
      >
        <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Архивировать приказ</h3>
        <p className="mt-1 text-sm text-zinc-500">Юридический статус приказа не изменится.</p>
        <label className="mt-3 block text-sm text-zinc-700 dark:text-zinc-300">
          Причина
          <select
            value={reasonCode}
            onChange={(e) => setReasonCode(e.target.value as (typeof REASON_OPTIONS)[number]["value"])}
            className="mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          >
            {REASON_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        {reasonCode === "other" ? (
          <textarea
            value={reasonText}
            onChange={(e) => setReasonText(e.target.value)}
            rows={3}
            className="mt-3 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
            placeholder="Текст причины"
          />
        ) : (
          <textarea
            value={reasonText}
            onChange={(e) => setReasonText(e.target.value)}
            rows={2}
            className="mt-3 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
            placeholder="Дополнительный комментарий (необязательно)"
          />
        )}
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
            className="rounded-lg border border-zinc-400 bg-zinc-100 px-3 py-2 text-sm font-medium text-zinc-900 disabled:opacity-60 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100"
          >
            {submitting ? "…" : "Архивировать"}
          </button>
        </div>
      </form>
    </div>
  );
}
