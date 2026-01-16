"use client";

import { useEffect, useState } from "react";
import type { EmployeeDetails } from "../_lib/types";
import { getEmployee, mapApiErrorToMessage } from "../_lib/api.client";

type Props = {
  employeeId: string | null;
  open: boolean;
  onClose: () => void;
  onTerminate: (details: EmployeeDetails) => void;
};

function isActive(d: EmployeeDetails): boolean {
  return d.date_to === null;
}

export default function EmployeeDrawer({ employeeId, open, onClose, onTerminate }: Props) {
  const [loading, setLoading] = useState(false);
  const [details, setDetails] = useState<EmployeeDetails | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;

    async function load() {
      if (!open || !employeeId) return;
      setLoading(true);
      setError(null);
      try {
        const d = await getEmployee(employeeId);
        if (alive) setDetails(d);
      } catch (e) {
        if (alive) setError(mapApiErrorToMessage(e));
      } finally {
        if (alive) setLoading(false);
      }
    }

    load();
    return () => {
      alive = false;
    };
  }, [employeeId, open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <div className="absolute right-0 top-0 h-full w-full max-w-xl bg-white shadow-xl border-l">
        <div className="p-4 border-b flex items-start justify-between">
          <div>
            <div className="font-semibold">
              {details?.full_name ?? (loading ? "Загрузка…" : "Сотрудник")}
            </div>
            <div className="text-sm text-gray-600">
              {details ? `Таб. № ${details.employee_id}` : ""}
            </div>
          </div>
          <button type="button" className="text-sm underline" onClick={onClose}>
            Закрыть
          </button>
        </div>

        <div className="p-4 space-y-3">
          {error ? (
            <div className="border rounded p-3 bg-white text-sm text-red-700">{error}</div>
          ) : null}

          {details ? (
            <div className="space-y-2 text-sm">
              <div className="border rounded p-3">
                <div className="font-semibold mb-2">Текущие данные</div>
                <div className="grid grid-cols-2 gap-2">
                  <div className="text-gray-600">Отдел</div>
                  <div>{details.department_name}</div>

                  <div className="text-gray-600">Должность</div>
                  <div>{details.position_name}</div>

                  <div className="text-gray-600">Ставка</div>
                  <div>{details.employment_rate}</div>

                  <div className="text-gray-600">Дата с</div>
                  <div>{details.date_from}</div>

                  <div className="text-gray-600">Дата по</div>
                  <div>{details.date_to ?? "—"}</div>
                </div>
              </div>

              {isActive(details) ? (
                <button
                  type="button"
                  className="border rounded px-3 py-2"
                  onClick={() => onTerminate(details)}
                >
                  Завершить работу
                </button>
              ) : null}
            </div>
          ) : loading ? (
            <div className="text-sm text-gray-600">Загрузка данных…</div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
