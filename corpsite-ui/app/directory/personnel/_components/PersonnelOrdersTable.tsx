"use client";

import * as React from "react";

import {
  formatPersonnelOrderDate,
  formatPersonnelOrderNumber,
  type PersonnelOrderListItem,
} from "../_lib/personnelOrdersApi.client";
import PersonnelOrderStatusBadge from "./PersonnelOrderStatusBadge";
import PersonnelOrderArchivedBadge from "./PersonnelOrderArchivedBadge";
import PersonnelOrderTypeBadge from "./PersonnelOrderTypeBadge";

export type PersonnelOrdersTableProps = {
  items: PersonnelOrderListItem[];
  loading?: boolean;
  emptyMessage?: string;
  onRowClick?: (row: PersonnelOrderListItem) => void;
  onPrintClick?: (row: PersonnelOrderListItem) => void;
};

function formatEmployees(row: PersonnelOrderListItem): string {
  const names = (row.employee_names || []).filter(Boolean);
  if (names.length > 0) return names.join(", ");
  const ids = row.employee_ids || [];
  if (ids.length > 0) return ids.map((id) => `#${id}`).join(", ");
  return "—";
}

const actionCellClass =
  "sticky right-0 z-[1] whitespace-nowrap border-l border-zinc-200 bg-white px-3 py-2 dark:border-zinc-800 dark:bg-zinc-950";
const actionHeaderClass =
  "sticky right-0 z-[1] border-l border-zinc-200 bg-zinc-50 px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/50";

export function PersonnelOrdersTable({
  items,
  loading = false,
  emptyMessage = "Приказы не найдены.",
  onRowClick,
  onPrintClick,
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
            <th className={actionHeaderClass}>Действия</th>
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
                {formatPersonnelOrderNumber(row.order_number)}
              </td>
              <td className="whitespace-nowrap px-3 py-2 text-zinc-700 dark:text-zinc-300">
                {formatPersonnelOrderDate(row.order_date)}
              </td>
              <td className="px-3 py-2">
                <PersonnelOrderTypeBadge typeCode={row.order_type_code} />
              </td>
              <td className="px-3 py-2">
                <div className="flex flex-wrap gap-1.5">
                  <PersonnelOrderStatusBadge status={row.status} />
                  {row.is_archived ? <PersonnelOrderArchivedBadge /> : null}
                </div>
              </td>
              <td className="max-w-[16rem] truncate px-3 py-2 text-zinc-700 dark:text-zinc-300">
                {formatEmployees(row)}
              </td>
              <td className="px-3 py-2 text-zinc-600 dark:text-zinc-400">{row.item_count}</td>
              <td className={actionCellClass}>
                <div className="flex flex-wrap items-center gap-2">
                  {onRowClick ? (
                    <button
                      type="button"
                      className="rounded-md border border-zinc-300 px-2 py-1 text-xs font-medium text-zinc-800 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-100 dark:hover:bg-zinc-900"
                      data-testid={`personnel-order-open-${row.order_id}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        onRowClick(row);
                      }}
                    >
                      Открыть
                    </button>
                  ) : null}
                  {onPrintClick ? (
                    <button
                      type="button"
                      className="rounded-md border border-zinc-300 bg-zinc-900 px-2 py-1 text-xs font-medium text-white hover:bg-zinc-800 dark:border-zinc-200 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
                      data-testid={`personnel-order-print-${row.order_id}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        onPrintClick(row);
                      }}
                    >
                      Печать
                    </button>
                  ) : null}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
