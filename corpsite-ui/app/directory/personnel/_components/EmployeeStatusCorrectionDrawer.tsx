"use client";

import * as React from "react";

export type EmployeeStatusCorrectionFormValues = {
  status: "working" | "not_working";
  expected_assignment_id?: number;
  expected_assignment_rate?: number | null;
  employment_rate?: number;
  reason?: string;
  comment?: string;
};

type Props = {
  open: boolean;
  fullName: string;
  currentStatus: "working" | "not_working";
  currentAssignmentId: number | null;
  currentRate: number | null;
  saving?: boolean;
  error?: string | null;
  onClose: () => void;
  onSubmit: (values: EmployeeStatusCorrectionFormValues) => Promise<void> | void;
};

export default function EmployeeStatusCorrectionDrawer({
  open,
  fullName,
  currentStatus,
  currentAssignmentId,
  currentRate,
  saving = false,
  error = null,
  onClose,
  onSubmit,
}: Props) {
  const [status, setStatus] = React.useState<"working" | "not_working">(currentStatus);
  const [rateInput, setRateInput] = React.useState(currentRate == null ? "" : String(currentRate));
  const [reason, setReason] = React.useState("");
  const [comment, setComment] = React.useState("");

  React.useEffect(() => {
    if (!open) return;
    setStatus(currentStatus);
    setRateInput(currentRate == null ? "" : String(currentRate));
    setReason("");
    setComment("");
  }, [open, currentStatus, currentRate, currentAssignmentId]);

  const normalizedRate = rateInput.trim().replace(",", ".");
  const rateIsValid = /^\d+(?:\.\d+)?$/.test(normalizedRate)
    && Number(normalizedRate) > 0 && Number(normalizedRate) <= 1.5;
  const rateChanged = rateIsValid && (currentRate == null || Number(normalizedRate) !== currentRate);
  const canSubmit = (status !== currentStatus || (currentAssignmentId != null && rateChanged))
    && (currentAssignmentId == null || rateIsValid || (currentRate == null && normalizedRate === ""));

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[70] flex" data-testid="employee-status-correction-drawer">
      <div className="absolute inset-0 bg-black/40" onClick={saving ? undefined : onClose} />
      <form
        className="relative ml-auto flex h-full w-full max-w-md flex-col border-l border-zinc-200 bg-white p-5 shadow-2xl dark:border-zinc-800 dark:bg-zinc-950"
        onSubmit={(event) => {
          event.preventDefault();
          if (!canSubmit || !reason.trim()) return;
          void onSubmit({
            status,
            ...(currentAssignmentId == null ? {} : {
              expected_assignment_id: currentAssignmentId,
              expected_assignment_rate: currentRate,
              ...(rateChanged ? { employment_rate: Number(normalizedRate) } : {}),
            }),
            reason: reason.trim(),
            comment: comment.trim() || undefined,
          });
        }}
      >
        <div className="flex items-start justify-between gap-3">
          <h2 className="text-lg font-semibold">Исправить статус и ставку</h2>
          <button
            type="button"
            disabled={saving}
            onClick={onClose}
            data-testid="employee-status-correction-close-top"
            className="rounded border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700"
          >
            Закрыть
          </button>
        </div>
        <p className="mt-1 text-sm text-zinc-500">Ручное исправление не создаёт кадровый приказ. Изменение ставки сохраняется в выбранном назначении.</p>
        {error ? <p className="mt-4 rounded border border-red-200 bg-red-50 p-2 text-sm text-red-700">{error}</p> : null}
        <div className="mt-5 grid gap-3 rounded border border-zinc-200 bg-zinc-50 p-3 text-sm dark:border-zinc-800 dark:bg-zinc-900/30">
          <div><span className="text-zinc-500">ФИО: </span><span data-testid="employee-status-correction-fio">{fullName || "—"}</span></div>
          <div><span className="text-zinc-500">Текущий статус: </span><span data-testid="employee-status-correction-current">{currentStatus === "working" ? "Работает" : "Не работает"}</span></div>
          <div><span className="text-zinc-500">Текущая ставка назначения: </span><span data-testid="employee-status-correction-current-rate">{currentRate ?? "—"}</span></div>
        </div>
        <label className="mt-5 grid gap-1 text-sm">
          <span>Статус</span>
          <select data-testid="employee-status-correction-select" value={status} onChange={(event) => setStatus(event.target.value as "working" | "not_working")} className="rounded border border-zinc-300 p-2 dark:border-zinc-700 dark:bg-zinc-950">
            <option value="working">Работает</option>
            <option value="not_working">Не работает</option>
          </select>
        </label>
        <label className="mt-4 grid gap-1 text-sm">
          <span>Ставка</span>
          <input data-testid="employee-status-correction-rate" inputMode="decimal" value={rateInput}
            disabled={currentAssignmentId == null}
            onChange={(event) => setRateInput(event.target.value)}
            className="rounded border border-zinc-300 p-2 dark:border-zinc-700 dark:bg-zinc-950" />
          {normalizedRate && !rateIsValid ? <span className="text-red-700">Ставка должна быть больше 0 и не больше 1,5.</span> : null}
        </label>
        <label className="mt-4 grid gap-1 text-sm">
          <span>Причина (обязательно)</span>
          <input required data-testid="employee-status-correction-reason" value={reason} onChange={(event) => setReason(event.target.value)} className="rounded border border-zinc-300 p-2 dark:border-zinc-700 dark:bg-zinc-950" />
        </label>
        <label className="mt-4 grid gap-1 text-sm">
          <span>Комментарий (необязательно)</span>
          <textarea data-testid="employee-status-correction-comment" value={comment} onChange={(event) => setComment(event.target.value)} rows={3} className="rounded border border-zinc-300 p-2 dark:border-zinc-700 dark:bg-zinc-950" />
        </label>
        <div className="mt-auto flex justify-end gap-2">
          <button type="button" disabled={saving} onClick={onClose} className="rounded border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700">Отмена</button>
          {!canSubmit ? (
            <span className="self-center text-sm text-zinc-500" data-testid="employee-status-correction-select-other-status">
              {currentAssignmentId == null ? "Ставка недоступна: нет однозначной связи с действующим основным назначением" : "Измените статус или ставку"}
            </span>
          ) : (
            <button type="submit" disabled={saving || !reason.trim()} data-testid="employee-status-correction-submit" className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white disabled:opacity-50">{saving ? "Сохранение…" : "Исправить статус и ставку"}</button>
          )}
        </div>
      </form>
    </div>
  );
}
