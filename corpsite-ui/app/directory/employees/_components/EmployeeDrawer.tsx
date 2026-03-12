// FILE: corpsite-ui/app/directory/employees/_components/EmployeeDrawer.tsx
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
      if (!open || !employeeId) {
        setDetails(null);
        setError(null);
        return;
      }

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
    (loading ? "Загрузка..." : "Сотрудник");

  const tabNo = details
    ? (details as any)?.id ?? (details as any)?.employee_id ?? employeeId
    : "";

  const orgUnitName =
    (details as any)?.org_unit?.name ??
    (details as any)?.orgUnit?.name ??
    (details as any)?.org_unit_name ??
    (details as any)?.orgUnitName ??
    null;

  const departmentName =
    (details as any)?.department?.name ??
    (details as any)?.department_name ??
    (details as any)?.departmentName ??
    orgUnitName ??
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
    <div className="fixed inset-0 z-50 flex">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative ml-auto flex h-full w-full max-w-[860px] flex-col border-l border-zinc-800 bg-[#050816] shadow-2xl">
        <div className="flex items-start justify-between gap-4 border-b border-zinc-800 px-6 py-5">
          <div className="min-w-0">
            <h2 className="truncate text-2xl font-semibold leading-tight text-zinc-100">{fio}</h2>
            <p className="mt-1 text-sm text-zinc-400">{details ? `Таб. № ${tabNo}` : ""}</p>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="shrink-0 rounded-lg border border-zinc-800 bg-zinc-950/40 px-4 py-2 text-sm text-zinc-200 transition hover:bg-zinc-900/60"
          >
            Закрыть
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5">
          {error ? (
            <div className="rounded-xl border border-red-900/60 bg-red-950/40 px-4 py-3 text-sm text-red-200">
              {error}
            </div>
          ) : null}

          {details ? (
            <div className="space-y-5">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
                <div className="rounded-xl border border-zinc-800 bg-zinc-950/30 p-4">
                  <div className="text-xs text-zinc-500">Статус</div>
                  <div className="mt-1 text-sm text-zinc-100">{statusLabel(details)}</div>
                </div>

                <div className="rounded-xl border border-zinc-800 bg-zinc-950/30 p-4">
                  <div className="text-xs text-zinc-500">Отдел</div>
                  <div className="mt-1 text-sm text-zinc-100">{departmentName}</div>
                </div>

                <div className="rounded-xl border border-zinc-800 bg-zinc-950/30 p-4">
                  <div className="text-xs text-zinc-500">Должность</div>
                  <div className="mt-1 text-sm text-zinc-100">{positionName}</div>
                </div>

                <div className="rounded-xl border border-zinc-800 bg-zinc-950/30 p-4">
                  <div className="text-xs text-zinc-500">Ставка</div>
                  <div className="mt-1 text-sm text-zinc-100">{String(rate)}</div>
                </div>

                <div className="rounded-xl border border-zinc-800 bg-zinc-950/30 p-4">
                  <div className="text-xs text-zinc-500">Дата с</div>
                  <div className="mt-1 text-sm text-zinc-100">{dateFrom}</div>
                </div>

                <div className="rounded-xl border border-zinc-800 bg-zinc-950/30 p-4">
                  <div className="text-xs text-zinc-500">Дата по</div>
                  <div className="mt-1 text-sm text-zinc-100">{dateTo}</div>
                </div>
              </div>

              <div className="rounded-xl border border-zinc-800 bg-zinc-950/30 p-4">
                <div className="text-xs text-zinc-500">Период работы</div>
                <div className="mt-2 text-sm text-zinc-100">
                  {dateFrom} — {dateTo}
                </div>
              </div>
            </div>
          ) : loading ? (
            <div className="text-sm text-zinc-400">Загрузка данных...</div>
          ) : null}
        </div>

        {details && isActive(details) ? (
          <div className="border-t border-zinc-800 px-6 py-4">
            <button
              type="button"
              className="rounded-lg border border-zinc-700 bg-zinc-950/50 px-4 py-2 text-sm text-zinc-100 transition hover:bg-zinc-900"
              onClick={() => onTerminate(details)}
            >
              Завершить работу
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
}