// FILE: corpsite-ui/app/directory/employees/_components/TerminateEmployeeDialog.tsx
"use client";

import { useEffect, useMemo, useState } from "react";

import type { EmployeeDetails } from "../_lib/types";
import { terminateEmployee, mapApiErrorToMessage } from "../_lib/api.client";

type Props = {
  employee: EmployeeDetails | null;
  open: boolean;
  onClose: () => void;
  onSubmitted: () => Promise<void> | void;
};

function fmt(v: unknown): string {
  if (v == null) return "—";
  const s = String(v).trim();
  return s ? s : "—";
}

export default function TerminateEmployeeDialog({ employee, open, onClose, onSubmitted }: Props) {
  const [dateTo, setDateTo] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Фиксируем значения, чтобы TS не ругался и чтобы замыкания были стабильны
  const employeeId = useMemo(() => (employee ? String(employee.id).trim() : ""), [employee]);
  const fullName = useMemo(() => (employee ? employee.fio : ""), [employee]);
  const dateFrom = useMemo(() => (employee ? employee.date_from : null), [employee]);

  useEffect(() => {
    if (!open) return;
    setError(null);

    // дефолт: сегодня (YYYY-MM-DD)
    const today = new Date();
    const iso = today.toISOString().slice(0, 10);
    setDateTo(iso);
  }, [open]);

  if (!open || !employee) return null;

  async function onSave() {
    if (!employeeId) return;

    setSubmitting(true);
    setError(null);

    try {
      await terminateEmployee(employeeId, dateTo);
      await onSubmitted();
    } catch (e) {
      setError(mapApiErrorToMessage(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/30" onClick={submitting ? undefined : onClose} />

      <div className="absolute left-1/2 top-1/2 w-full max-w-lg -translate-x-1/2 -translate-y-1/2 bg-white border rounded shadow-xl">
        <div className="p-4 border-b">
          <div className="font-semibold">Завершить работу сотрудника</div>
          <div className="text-sm text-gray-600 mt-1">
            {fmt(fullName)} (Таб. № {fmt(employeeId)})
          </div>
        </div>

        <div className="p-4 space-y-3">
          {error ? <div className="border rounded p-3 bg-white text-sm text-red-700">{error}</div> : null}

          <div>
            <label className="block text-xs text-gray-600 mb-1">Дата по</label>
            <input
              type="date"
              className="w-full border rounded px-3 py-2 text-sm"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              disabled={submitting}
            />
            <div className="text-xs text-gray-500 mt-1">Дата по не может быть раньше даты с ({fmt(dateFrom)}).</div>
          </div>
        </div>

        <div className="p-4 border-t flex justify-end gap-2">
          <button type="button" className="border rounded px-3 py-2" onClick={onClose} disabled={submitting}>
            Отмена
          </button>
          <button
            type="button"
            className="border rounded px-3 py-2"
            onClick={onSave}
            disabled={submitting || !dateTo || !employeeId}
          >
            {submitting ? "Сохранение…" : "Сохранить"}
          </button>
        </div>
      </div>
    </div>
  );
}
