// FILE: corpsite-ui/app/directory/employees/_components/EmployeesTable.tsx
"use client";

import type { EmployeeListItem } from "../_lib/types";

type Props = {
  items: EmployeeListItem[];
  total: number;
  limit: number;
  offset: number;
  loading: boolean;
  onOpenEmployee: (employee_id: string) => void;
  onTerminateEmployee: (employee_id: string, employee_name: string) => Promise<void> | void;
  onChangePage: (nextOffset: number) => void;
};

function formatDate(d: string | null): string {
  if (!d) return "—";
  const dt = new Date(d);
  if (Number.isNaN(dt.getTime())) return d;
  return dt.toLocaleDateString("ru-RU");
}

function computeIsActive(it: any): boolean {
  if (typeof it?.status === "string") {
    const s = String(it.status).toLowerCase();
    if (s === "active") return true;
    if (s === "inactive") return false;
  }

  if (typeof it?.is_active === "boolean") return it.is_active;
  if (typeof it?.isActive === "boolean") return it.isActive;
  if ("date_to" in (it ?? {})) return it.date_to == null;
  if ("dateTo" in (it ?? {})) return it.dateTo == null;
  return true;
}

function statusMeta(it: any): { active: boolean; label: string } {
  const active = computeIsActive(it);
  return { active, label: active ? "Работает" : "Не работает" };
}

function StatusBadge({ it }: { it: any }) {
  const meta = statusMeta(it);
  const cls = meta.active
    ? "bg-emerald-100 text-emerald-800"
    : "bg-zinc-200 text-zinc-700";

  return <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${cls}`}>{meta.label}</span>;
}

function getEmployeeId(it: any): string {
  const v = it?.employee_id ?? it?.employeeId ?? it?.id;
  return v == null ? "" : String(v);
}

function getEmployeeFio(it: any): string {
  return it?.fio ?? it?.full_name ?? it?.fullName ?? it?.name ?? it?.title ?? "—";
}

function getDepartmentName(it: any): string {
  return it?.department_name ?? it?.departmentName ?? it?.department?.name ?? it?.org_unit?.name ?? "—";
}

function getPositionName(it: any): string {
  return it?.position_name ?? it?.positionName ?? it?.position?.name ?? it?.position?.title ?? "—";
}

export default function EmployeesTable({
  items,
  total,
  limit,
  offset,
  loading,
  onOpenEmployee,
  onTerminateEmployee,
  onChangePage,
}: Props) {
  const page = Math.floor(offset / limit) + 1;
  const pages = Math.max(1, Math.ceil(Math.max(total, 1) / limit));

  return (
    <div className="overflow-hidden rounded-xl border border-zinc-200">
      <div className="overflow-x-auto">
        <table className="min-w-full border-collapse">
          <thead>
            <tr className="bg-zinc-100 text-left">
              <th className="w-[72px] px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-600">
                Таб. №
              </th>
              <th className="min-w-[300px] px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-600">
                ФИО
              </th>
              <th className="min-w-[220px] px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-600">
                Отдел
              </th>
              <th className="min-w-[220px] px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-600">
                Должность
              </th>
              <th className="w-[100px] px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-600">
                Ставка
              </th>
              <th className="w-[110px] px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-600">
                Дата с
              </th>
              <th className="w-[110px] px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-600">
                Дата по
              </th>
              <th className="w-[120px] px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-600">
                Статус
              </th>
              <th className="w-[220px] px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-600">
                Действия
              </th>
            </tr>
          </thead>

          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={9} className="px-3 py-2.5 text-[13px] text-zinc-600">
                  {loading ? "Загрузка..." : "Записи не найдены."}
                </td>
              </tr>
            ) : (
              (items as any[]).map((it) => {
                const employeeId = getEmployeeId(it);
                const fio = getEmployeeFio(it);
                const active = computeIsActive(it);

                return (
                  <tr key={employeeId || fio} className="border-t border-zinc-200 align-middle">
                    <td className="px-3 py-1.5 text-[13px] leading-4 text-zinc-900">
                      {employeeId || "—"}
                    </td>

                    <td className="px-3 py-1.5 text-[13px] leading-4 text-zinc-900">
                      {fio}
                    </td>

                    <td className="px-3 py-1.5 text-[13px] leading-4 text-zinc-600">
                      {getDepartmentName(it)}
                    </td>

                    <td className="px-3 py-1.5 text-[13px] leading-4 text-zinc-600">
                      {getPositionName(it)}
                    </td>

                    <td className="px-3 py-1.5 text-[13px] leading-4 text-zinc-600">
                      {it.employment_rate ?? it.rate ?? "—"}
                    </td>

                    <td className="px-3 py-1.5 text-[13px] leading-4 text-zinc-600">
                      {formatDate(it.date_from ?? it.dateFrom ?? null)}
                    </td>

                    <td className="px-3 py-1.5 text-[13px] leading-4 text-zinc-600">
                      {formatDate(it.date_to ?? it.dateTo ?? null)}
                    </td>

                    <td className="px-3 py-1.5">
                      <StatusBadge it={it} />
                    </td>

                    <td className="px-3 py-1.5">
                      <div className="flex items-center gap-1.5">
                        {!!employeeId && (
                          <button
                            type="button"
                            onClick={() => onOpenEmployee(employeeId)}
                            className="rounded-md border border-zinc-200 bg-zinc-100 px-2.5 py-1 text-[12px] leading-4 text-zinc-900 transition hover:bg-zinc-200"
                          >
                            Открыть
                          </button>
                        )}

                        {!!employeeId && active && (
                          <button
                            type="button"
                            onClick={() => onTerminateEmployee(employeeId, fio)}
                            className="rounded-md border border-zinc-200 bg-zinc-100 px-2.5 py-1 text-[12px] leading-4 text-zinc-900 transition hover:bg-zinc-200"
                          >
                            Завершить
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between border-t border-zinc-200 px-3 py-2 text-sm">
        <div className="text-zinc-600">
          Страница {page} из {pages}
          {loading ? " (обновление...)" : ""}
        </div>

        <div className="flex gap-2">
          <button
            type="button"
            className="rounded border border-zinc-200 bg-zinc-100 px-3 py-1 text-zinc-800 transition hover:bg-zinc-200 disabled:opacity-50"
            disabled={offset <= 0 || loading}
            onClick={() => onChangePage(Math.max(0, offset - limit))}
          >
            Назад
          </button>

          <button
            type="button"
            className="rounded border border-zinc-200 bg-zinc-100 px-3 py-1 text-zinc-800 transition hover:bg-zinc-200 disabled:opacity-50"
            disabled={offset + limit >= total || loading}
            onClick={() => onChangePage(offset + limit)}
          >
            Вперёд
          </button>
        </div>
      </div>
    </div>
  );
}