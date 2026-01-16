// corpsite-ui/app/directory/employees/_components/EmployeesTable.tsx

"use client";

import Link from "next/link";
import type { EmployeeListItem } from "../_lib/types";

type Props = {
  items: EmployeeListItem[];
  total: number;
  limit: number;
  offset: number;
  loading: boolean;
  onOpenEmployee: (employee_id: string) => void;
  onChangePage: (nextOffset: number) => void;
};

function formatDate(d: string | null): string {
  if (!d) return "—";
  return d;
}

function computeIsActive(it: any): boolean {
  if (typeof it.is_active === "boolean") return it.is_active;
  if (typeof it.isActive === "boolean") return it.isActive;
  if ("date_to" in it) return it.date_to == null;
  if ("dateTo" in it) return it.dateTo == null;
  return true;
}

function StatusBadge({ active }: { active: boolean }) {
  const label = active ? "Работает" : "Уволен";
  const cls = active
    ? "bg-green-100 text-green-800"
    : "bg-gray-100 text-gray-700";
  return <span className={`px-2 py-1 rounded text-xs ${cls}`}>{label}</span>;
}

export default function EmployeesTable({
  items,
  total,
  limit,
  offset,
  loading,
  onOpenEmployee,
  onChangePage,
}: Props) {
  const page = Math.floor(offset / limit) + 1;
  const pages = Math.max(1, Math.ceil(total / limit));

  const getId = (it: any): string => String(it.employee_id ?? it.id ?? "");
  const hrefOf = (employee_id: string) =>
    `/directory/employees/${encodeURIComponent(employee_id)}`;

  return (
    <div className="border rounded bg-white overflow-hidden">
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 text-gray-700">
            <tr>
              <th className="text-left px-3 py-2">Таб. №</th>
              <th className="text-left px-3 py-2">ФИО</th>
              <th className="text-left px-3 py-2">Отдел</th>
              <th className="text-left px-3 py-2">Должность</th>
              <th className="text-left px-3 py-2">Ставка</th>
              <th className="text-left px-3 py-2">Дата с</th>
              <th className="text-left px-3 py-2">Дата по</th>
              <th className="text-left px-3 py-2">Статус</th>
              <th className="text-right px-3 py-2">Действия</th>
            </tr>
          </thead>

          <tbody>
            {items.length === 0 ? (
              <tr>
                <td className="px-3 py-6 text-gray-600" colSpan={9}>
                  Ничего не найдено.
                </td>
              </tr>
            ) : (
              (items as any[]).map((it) => {
                const employee_id = getId(it);
                const active = computeIsActive(it);
                const rowCls = !active ? "text-gray-600" : "text-gray-900";

                return (
                  <tr key={employee_id} className={rowCls}>
                    <td className="px-3 py-2 whitespace-nowrap">
                      {employee_id}
                    </td>

                    <td className="px-3 py-2">
                      <Link
                        href={hrefOf(employee_id)}
                        className="underline text-blue-700 hover:text-blue-900"
                        onClick={() => {
                          try {
                            onOpenEmployee(employee_id);
                          } catch {}
                        }}
                      >
                        {it.full_name ?? it.fullName}
                      </Link>
                    </td>

                    <td className="px-3 py-2">
                      {it.department_name ?? it.departmentName}
                    </td>
                    <td className="px-3 py-2">
                      {it.position_name ?? it.positionName}
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap">
                      {it.employment_rate ?? it.rate ?? "—"}
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap">
                      {formatDate(it.date_from ?? it.dateFrom ?? null)}
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap">
                      {formatDate(it.date_to ?? it.dateTo ?? null)}
                    </td>

                    <td className="px-3 py-2">
                      <StatusBadge active={active} />
                    </td>

                    <td className="px-3 py-2 text-right">
                      <Link
                        href={hrefOf(employee_id)}
                        className="underline text-blue-700 hover:text-blue-900"
                        onClick={() => {
                          try {
                            onOpenEmployee(employee_id);
                          } catch {}
                        }}
                      >
                        Просмотр
                      </Link>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between px-3 py-2 border-t text-sm">
        <div className="text-gray-600">
          Страница {page} из {pages}
          {loading ? " (обновление…)" : ""}
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            className="border rounded px-3 py-1 disabled:opacity-50"
            disabled={offset <= 0 || loading}
            onClick={() => onChangePage(Math.max(0, offset - limit))}
          >
            Назад
          </button>
          <button
            type="button"
            className="border rounded px-3 py-1 disabled:opacity-50"
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
