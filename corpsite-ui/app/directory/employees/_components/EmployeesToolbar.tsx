"use client";

import type { Department, Position } from "../_lib/types";
import type { EmployeesFilters } from "../_lib/query";

type Props = {
  filters: EmployeesFilters;
  departments: Department[];
  positions: Position[];
  onChange: (partial: Partial<EmployeesFilters>) => void;
  onReset: () => void;
};

export default function EmployeesToolbar({
  filters,
  departments,
  positions,
  onChange,
  onReset,
}: Props) {
  return (
    <div className="border rounded p-3 bg-white">
      <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end">
        <div className="md:col-span-4">
          <label className="block text-xs text-gray-600 mb-1">Поиск</label>
          <input
            className="w-full border rounded px-3 py-2 text-sm"
            value={filters.q ?? ""}
            onChange={(e) => onChange({ q: e.target.value })}
            placeholder="ФИО или таб. №"
          />
        </div>

        <div className="md:col-span-3">
          <label className="block text-xs text-gray-600 mb-1">Отдел</label>
          <select
            className="w-full border rounded px-3 py-2 text-sm"
            value={filters.department_id ?? ""}
            onChange={(e) =>
              onChange({ department_id: e.target.value ? Number(e.target.value) : undefined })
            }
          >
            <option value="">Все</option>
            {departments.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </div>

        <div className="md:col-span-3">
          <label className="block text-xs text-gray-600 mb-1">Должность</label>
          <select
            className="w-full border rounded px-3 py-2 text-sm"
            value={filters.position_id ?? ""}
            onChange={(e) =>
              onChange({ position_id: e.target.value ? Number(e.target.value) : undefined })
            }
          >
            <option value="">Все</option>
            {positions.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>

        <div className="md:col-span-2">
          <label className="block text-xs text-gray-600 mb-1">Статус</label>
          <select
            className="w-full border rounded px-3 py-2 text-sm"
            value={filters.status ?? "active"}
            onChange={(e) => onChange({ status: e.target.value as any })}
          >
            <option value="active">Активные</option>
            <option value="inactive">Уволенные</option>
            <option value="all">Все</option>
          </select>
        </div>

        <div className="md:col-span-12 flex justify-end">
          <button className="text-sm underline" onClick={onReset} type="button">
            Сбросить фильтры
          </button>
        </div>
      </div>
    </div>
  );
}
