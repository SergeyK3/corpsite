"use client";

import * as React from "react";

import {
  formatPersonnelOrderDate,
  type PersonnelOrderListItem,
} from "../_lib/personnelOrdersApi.client";
import PersonnelOrderStatusBadge from "./PersonnelOrderStatusBadge";
import PersonnelOrderTypeBadge from "./PersonnelOrderTypeBadge";

export type PersonnelOrdersTableProps = {
  items: PersonnelOrderListItem[];
  loading?: boolean;
  emptyMessage?: string;
  onRowClick?: (row: PersonnelOrderListItem) => void;
};

function formatEmployees(row: PersonnelOrderListItem): string {
  const names = (row.employee_names || []).filter(Boolean);
  if (names.length > 0) return names.join(", ");
  const ids = row.employee_ids || [];
  if (ids.length > 0) return ids.map((id) => `#${id}`).join(", ");
  return "—";
}

export function PersonnelOrdersTable({
  items,
  loading = false,
  emptyMessage = "Приказы не найдены.",
  onRowClick,
}: PersonnelOrdersTableProps) {
  if (loading) {
    return (
      <div
        data-testid="personnel-orders-loading"
        className="rounded-xl border border-zinc-200 px-4 py-8 text-center text-sm text-zinc-500 dark:border-zinc-800"
      >
        Загрузка приказов…
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div
        data-testid="personnel-orders-empty"
        className="rounded-xl border border-dashed border-zinc-300 px-4 py-10 text-center text-sm text-zinc-500 dark:border-zinc-700 dark:text-zinc-400"
      >
        {emptyMessage}
      </div>
    );
  }

  return (
    <div
      data-testid="personnel-orders-table"
      className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800"
    >
      <table className="min-w-full divide-y divide-zinc-200 text-sm dark:divide-zinc-800">
        <thead className="bg-zinc-50 dark:bg-zinc-900/50">
          <tr>
            {["№ приказа", "Дата", "Тип", "Статус", "Сотрудники", "Пунктов"].map((header) => (
              <th
                key={header}
                className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-zinc-500"
              >
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-100 bg-white dark:divide-zinc-800 dark:bg-zinc-950">
          {items.map((row) => (
            <tr
              key={row.order_id}
              data-testid={`personnel-order-row-${row.order_id}`}
              className={onRowClick ? "cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-900/40" : undefined}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
            >
              <td className="whitespace-nowrap px-3 py-2 font-medium text-zinc-900 dark:text-zinc-100">
                {row.order_number}
              </td>
              <td className="whitespace-nowrap px-3 py-2 text-zinc-700 dark:text-zinc-300">
                {formatPersonnelOrderDate(row.order_date)}
              </td>
              <td className="px-3 py-2">
                <PersonnelOrderTypeBadge typeCode={row.order_type_code} />
              </td>
              <td className="px-3 py-2">
                <PersonnelOrderStatusBadge status={row.status} />
              </td>
              <td className="max-w-[16rem] truncate px-3 py-2 text-zinc-700 dark:text-zinc-300">
                {formatEmployees(row)}
              </td>
              <td className="px-3 py-2 text-zinc-600 dark:text-zinc-400">{row.item_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
