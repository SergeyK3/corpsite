// FILE: corpsite-ui/app/directory/employees/_components/EmployeeDrawer.tsx
"use client";

import { useEffect, useState } from "react";
import type { EmployeeDetails } from "../_lib/types";
import { getEmployee, mapApiErrorToMessage } from "../_lib/api.client";
import { employeeStatusMeta } from "../_lib/employeeStatus";
import EmployeeStatusBadge from "./EmployeeStatusBadge";

type Props = {
  employeeId: string | null;
  open: boolean;
  onClose: () => void;
  onTerminate: (details: EmployeeDetails) => void;
  onCreateUser?: (details: EmployeeDetails) => void;
  refreshToken?: number;
};

function fmtDate(v: string | null | undefined): string {
  if (!v) return "—";
  const dt = new Date(v);
  if (Number.isNaN(dt.getTime())) return String(v);
  return dt.toLocaleDateString("ru-RU");
}

function isActive(d: EmployeeDetails): boolean {
  return employeeStatusMeta(d).active;
}

export default function EmployeeDrawer({
  employeeId,
  open,
  onClose,
  onTerminate,
  onCreateUser,
  refreshToken = 0,
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
  }, [employeeId, open, refreshToken]);

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

  const linkedUser = (details as any)?.user ?? null;

  function userStatusLabel(active: boolean | null | undefined): string {
    if (active === true) return "Активен";
    if (active === false) return "Неактивен";
    return "—";
  }

  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="absolute inset-0 bg-zinc-600/35 dark:bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <div className="relative ml-auto flex h-full w-full max-w-[860px] flex-col border-l border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 shadow-2xl">
        <div className="flex items-start justify-between gap-4 border-b border-zinc-200 dark:border-zinc-800 px-6 py-5">
          <div className="min-w-0">
            <h2 className="truncate text-2xl font-semibold leading-tight text-zinc-900 dark:text-zinc-50">{fio}</h2>
            <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{details ? `Таб. № ${tabNo}` : ""}</p>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="shrink-0 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700"
          >
            Закрыть
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5">
          {error ? (
            <div className="rounded-xl border border-red-200 dark:border-red-900/55 bg-red-50 dark:bg-red-950/35 px-4 py-3 text-sm text-red-800 dark:text-red-200">
              {error}
            </div>
          ) : null}

          {details ? (
            <div className="space-y-5">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
                <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4">
                  <div className="text-xs text-zinc-600 dark:text-zinc-400">Статус</div>
                  <div className="mt-1">
                    <EmployeeStatusBadge item={details} />
                  </div>
                </div>

                <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4">
                  <div className="text-xs text-zinc-600 dark:text-zinc-400">Отдел</div>
                  <div className="mt-1 text-sm text-zinc-900 dark:text-zinc-50">{departmentName}</div>
                </div>

                <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4">
                  <div className="text-xs text-zinc-600 dark:text-zinc-400">Должность</div>
                  <div className="mt-1 text-sm text-zinc-900 dark:text-zinc-50">{positionName}</div>
                </div>

                <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4">
                  <div className="text-xs text-zinc-600 dark:text-zinc-400">Ставка</div>
                  <div className="mt-1 text-sm text-zinc-900 dark:text-zinc-50">{String(rate)}</div>
                </div>

                <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4">
                  <div className="text-xs text-zinc-600 dark:text-zinc-400">Дата с</div>
                  <div className="mt-1 text-sm text-zinc-900 dark:text-zinc-50">{dateFrom}</div>
                </div>

                <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4">
                  <div className="text-xs text-zinc-600 dark:text-zinc-400">Дата по</div>
                  <div className="mt-1 text-sm text-zinc-900 dark:text-zinc-50">{dateTo}</div>
                </div>
              </div>

              <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4">
                <div className="text-xs text-zinc-600 dark:text-zinc-400">Период работы</div>
                <div className="mt-2 text-sm text-zinc-900 dark:text-zinc-50">
                  {dateFrom} — {dateTo}
                </div>
              </div>

              <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4">
                <div className="text-xs text-zinc-600 dark:text-zinc-400">Аккаунт</div>
                {linkedUser ? (
                  <div className="mt-2 space-y-1 text-sm text-zinc-900 dark:text-zinc-50">
                    <div>
                      <span className="text-zinc-600 dark:text-zinc-400">Логин: </span>
                      {linkedUser.login ?? "—"}
                    </div>
                    <div>
                      <span className="text-zinc-600 dark:text-zinc-400">Роль: </span>
                      {linkedUser.role_name ?? linkedUser.role_id ?? "—"}
                    </div>
                    <div>
                      <span className="text-zinc-600 dark:text-zinc-400">Статус: </span>
                      {userStatusLabel(linkedUser.is_active)}
                    </div>
                  </div>
                ) : (
                  <div className="mt-2 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div className="text-sm text-zinc-700 dark:text-zinc-300">Аккаунт не создан</div>
                    {onCreateUser ? (
                      <button
                        type="button"
                        onClick={() => onCreateUser(details)}
                        className="shrink-0 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-500"
                      >
                        Создать пользователя
                      </button>
                    ) : null}
                  </div>
                )}
              </div>
            </div>
          ) : loading ? (
            <div className="text-sm text-zinc-600 dark:text-zinc-400">Загрузка данных...</div>
          ) : null}
        </div>

        {details && isActive(details) ? (
          <div className="border-t border-zinc-200 dark:border-zinc-800 px-6 py-4">
            <button
              type="button"
              className="rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white/50 dark:bg-zinc-900/50 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 transition hover:bg-zinc-200 dark:hover:bg-zinc-700"
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