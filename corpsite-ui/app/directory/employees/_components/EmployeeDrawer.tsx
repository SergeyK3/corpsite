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

function fmtDate(v: string | null | undefined): string {
  if (!v) return "—";
  const dt = new Date(v);
  if (Number.isNaN(dt.getTime())) return String(v);
  return dt.toLocaleDateString("ru-RU");
}

function statusLabel(details: any): string {
  const s = (details?.status ?? "").toString().toLowerCase();
  if (s === "active") return "Работает";
  if (s === "inactive") return "Не работает";
  return "—";
}

function isActive(d: EmployeeDetails): boolean {
  const s = (d as any)?.status?.toString?.().toLowerCase?.();
  if (s === "active") return true;
  if (s === "inactive") return false;
  return (d as any)?.date_to === null;
}

export default function EmployeeDrawer({
  employeeId,
  open,
  onClose,
  onTerminate,
}: Props) {
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

  const fio =
    (details as any)?.fio ??
    (details as any)?.full_name ??
    (details as any)?.fullName ??
    (loading ? "Загрузка…" : "Сотрудник");

  const tabNo = details
    ? (details as any)?.id ?? (details as any)?.employee_id ?? employeeId
    : "";

  const departmentName =
    (details as any)?.department?.name ??
    (details as any)?.department_name ??
    (details as any)?.departmentName ??
    "—";

  const positionName =
    (details as any)?.position?.name ??
    (details as any)?.position_name ??
    (details as any)?.positionName ??
    "—";

  const rate = (details as any)?.employment_rate ?? (details as any)?.rate ?? "—";

  const dateFrom = fmtDate((details as any)?.date_from ?? (details as any)?.dateFrom);
  const dateTo = fmtDate((details as any)?.date_to ?? (details as any)?.dateTo);

  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <div className="absolute right-0 top-0 h-full w-full max-w-xl bg-white shadow-xl border-l">
        <div className="p-4 border-b flex items-start justify-between">
          <div>
            <div className="font-semibold text-gray-900">{fio}</div>
            <div className="text-sm text-gray-800">
              {details ? `Таб. № ${tabNo}` : ""}
            </div>
          </div>
          <button
            type="button"
            className="text-sm underline text-gray-900"
            onClick={onClose}
          >
            Закрыть
          </button>
        </div>

        <div className="p-4 space-y-3">
          {error ? (
            <div className="border rounded p-3 bg-white text-sm text-red-700">
              {error}
            </div>
          ) : null}

          {details ? (
            <div className="space-y-2 text-sm text-gray-900">
              <div className="border rounded p-3">
                <div className="font-semibold mb-2 text-gray-900">Текущие данные</div>

                <div className="grid grid-cols-2 gap-2">
                  {/* ЛЕВАЯ колонка — подписи */}
                  <div className="text-gray-700">Статус</div>
                  {/* ПРАВАЯ колонка — значения (делаем темнее) */}
                  <div className="text-gray-900 font-medium">{statusLabel(details)}</div>

                  <div className="text-gray-700">Отдел</div>
                  <div className="text-gray-900 font-medium">{departmentName}</div>

                  <div className="text-gray-700">Должность</div>
                  <div className="text-gray-900 font-medium">{positionName}</div>

                  <div className="text-gray-700">Ставка</div>
                  <div className="text-gray-900 font-medium">{String(rate)}</div>

                  <div className="text-gray-700">Дата с</div>
                  <div className="text-gray-900 font-medium">{dateFrom}</div>

                  <div className="text-gray-700">Дата по</div>
                  <div className="text-gray-900 font-medium">{dateTo}</div>

                  <div className="text-gray-700">Период</div>
                  <div className="text-gray-900 font-medium">
                    {dateFrom} — {dateTo}
                  </div>
                </div>
              </div>

              {isActive(details) ? (
                <button
                  type="button"
                  className="border rounded px-3 py-2 text-gray-900 hover:bg-gray-50"
                  onClick={() => onTerminate(details)}
                >
                  Завершить работу
                </button>
              ) : null}
            </div>
          ) : loading ? (
            <div className="text-sm text-gray-800">Загрузка данных…</div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
