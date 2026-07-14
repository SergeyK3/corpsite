"use client";

import * as React from "react";

import type { EmployeeDetails } from "../../employees/_lib/types";

export type EmployeeGeneralCorrectionFormValues = {
  full_name: string;
  effective_date: string;
  reason: string;
  comment: string;
};

type Props = {
  open: boolean;
  details: EmployeeDetails | null;
  saving?: boolean;
  error?: string | null;
  onClose: () => void;
  onSubmit: (values: EmployeeGeneralCorrectionFormValues) => Promise<void> | void;
};

function todayIsoDate(): string {
  return new Date().toISOString().slice(0, 10);
}

function initialFullName(details: EmployeeDetails | null): string {
  if (!details) return "";
  const d = details as Record<string, unknown>;
  return String(d.fio ?? d.full_name ?? d.fullName ?? "").trim();
}

export default function EmployeeGeneralCorrectionDrawer({
  open,
  details,
  saving = false,
  error = null,
  onClose,
  onSubmit,
}: Props) {
  const [fullName, setFullName] = React.useState("");
  const [effectiveDate, setEffectiveDate] = React.useState(todayIsoDate());
  const [reason, setReason] = React.useState("");
  const [comment, setComment] = React.useState("");

  React.useEffect(() => {
    if (!open || !details) return;
    setFullName(initialFullName(details));
    setEffectiveDate(todayIsoDate());
    setReason("");
    setComment("");
  }, [open, details]);

  React.useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && open && !saving) onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose, saving]);

  if (!open || !details) return null;

  return (
    <div className="fixed inset-0 z-[60] flex" data-testid="general-correction-drawer">
      <div
        className="absolute inset-0 bg-zinc-600/35 backdrop-blur-sm dark:bg-black/50"
        onClick={saving ? undefined : onClose}
      />
      <div className="relative ml-auto flex h-full w-full max-w-[720px] flex-col border-l border-zinc-200 bg-white shadow-2xl dark:border-zinc-800 dark:bg-zinc-950">
        <div className="flex items-start justify-between border-b border-zinc-200 px-5 py-4 dark:border-zinc-800">
          <div>
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Исправить данные</h2>
            <p className="mt-1 text-sm text-zinc-500">Административная корректировка общих сведений сотрудника.</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="rounded border border-zinc-300 px-2 py-1 text-sm dark:border-zinc-700"
          >
            Закрыть
          </button>
        </div>

        <form
          className="flex flex-1 flex-col overflow-y-auto px-5 py-4"
          onSubmit={(e) => {
            e.preventDefault();
            void onSubmit({
              full_name: fullName.trim(),
              effective_date: effectiveDate,
              reason: reason.trim(),
              comment: comment.trim(),
            });
          }}
        >
          {error ? (
            <div className="mb-4 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-200">
              {error}
            </div>
          ) : null}

          <div className="space-y-4">
            <label className="grid gap-1">
              <span className="text-xs font-medium text-zinc-500">ФИО *</span>
              <input
                data-testid="general-correction-full-name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                required
              />
            </label>

            <label className="grid gap-1">
              <span className="text-xs font-medium text-zinc-500">Дата корректировки *</span>
              <input
                data-testid="general-correction-effective-date"
                type="date"
                value={effectiveDate}
                onChange={(e) => setEffectiveDate(e.target.value)}
                className="rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                required
              />
            </label>

            <label className="grid gap-1">
              <span className="text-xs font-medium text-zinc-500">Причина *</span>
              <input
                data-testid="general-correction-reason"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                className="rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                required
              />
            </label>

            <label className="grid gap-1">
              <span className="text-xs font-medium text-zinc-500">Комментарий *</span>
              <textarea
                data-testid="general-correction-comment"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                rows={3}
                className="rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                required
              />
            </label>
          </div>

          <div className="mt-auto flex justify-end gap-2 border-t border-zinc-200 pt-4 dark:border-zinc-800">
            <button
              type="button"
              onClick={onClose}
              disabled={saving}
              className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700"
            >
              Отмена
            </button>
            <button
              type="submit"
              disabled={saving}
              data-testid="general-correction-submit"
              className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? "Сохранение…" : "Сохранить корректировку"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
