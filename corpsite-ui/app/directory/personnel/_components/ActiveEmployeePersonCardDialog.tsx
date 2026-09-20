"use client";

import * as React from "react";
import {
  applyActiveEmployeePersonCard,
  type ActiveEmployeePersonCardApplyResponse,
  type ActiveEmployeePersonCardPreflight,
} from "../_lib/personnelMigrationApi.client";

type Props = {
  employeeId: number;
  employeeName: string;
  preflight: ActiveEmployeePersonCardPreflight;
  onClose: () => void;
  onCreated: (result: ActiveEmployeePersonCardApplyResponse) => void;
};

function requestId(employeeId: number): string {
  return `active-employee-card-${employeeId}-${globalThis.crypto?.randomUUID?.() ?? Date.now()}`;
}

export default function ActiveEmployeePersonCardDialog({ employeeId, employeeName, preflight, onClose, onCreated }: Props) {
  const [confirmed, setConfirmed] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const canApply = preflight.ready && !!preflight.expected_precondition && confirmed && !busy;

  async function apply() {
    if (!canApply || !preflight.expected_precondition) return;
    setBusy(true); setError(null);
    try {
      const result = await applyActiveEmployeePersonCard({ employee_id: employeeId, expected_precondition: preflight.expected_precondition, request_id: requestId(employeeId) });
      onCreated(result);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Не удалось создать личную карточку.");
      setBusy(false);
    }
  }

  return <div role="dialog" aria-modal="true" aria-label="Создание личной карточки" className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
    <div className="max-h-[90vh] w-full max-w-xl overflow-auto rounded-xl bg-white p-6 shadow-xl dark:bg-zinc-950">
      <div className="flex items-start justify-between gap-4"><div><h2 className="text-lg font-semibold">Создать рабочую личную карточку</h2><p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">Действующий сотрудник: {employeeName}</p></div><button type="button" onClick={onClose}>Закрыть</button></div>
      <dl className="mt-4 grid grid-cols-2 gap-3 text-sm"><div><dt className="text-zinc-500">Employee</dt><dd>{employeeId}</dd></div><div><dt className="text-zinc-500">ИИН</dt><dd>{preflight.iin.present ? `••••••${preflight.iin.last4 ?? ""}` : "не найден"}</dd></div><div><dt className="text-zinc-500">Статус</dt><dd>{preflight.operational_status ?? "—"}</dd></div></dl>
      {preflight.blockers.length ? <section className="mt-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-800 dark:bg-red-950/30 dark:text-red-200"><h3 className="font-medium">Создание сейчас недоступно</h3><ul className="mt-2 list-disc space-y-1 pl-5">{preflight.blockers.map((blocker) => <li key={blocker.code}><strong>{blocker.code}</strong>: {blocker.detail}</li>)}</ul></section> : <section className="mt-4 rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950 dark:bg-amber-950/30 dark:text-amber-100"><p>Будет создана и связана только личная карточка Person. Текущее назначение, подразделение, должность, ставка и даты не изменятся.</p><label className="mt-3 flex gap-2"><input aria-label="Подтверждаю создание личной карточки" type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />Я подтверждаю создание личной карточки действующего сотрудника.</label></section>}
      {error ? <p role="status" className="mt-3 text-sm text-red-700">{error}</p> : null}
      <div className="mt-5 flex gap-2"><button type="button" disabled={!canApply} onClick={() => void apply()} className="rounded bg-blue-600 px-4 py-2 text-sm text-white disabled:opacity-50">{busy ? "Создание…" : "Подтвердить создание"}</button><button type="button" onClick={onClose} className="rounded border px-4 py-2 text-sm">Отмена</button></div>
    </div>
  </div>;
}
