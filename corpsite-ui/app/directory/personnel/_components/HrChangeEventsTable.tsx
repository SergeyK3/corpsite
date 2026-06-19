"use client";

import * as React from "react";

import {
  formatHrChangeEventDate,
  formatHrChangeEventValue,
  type HrChangeEventRow,
} from "../_lib/hrChangeEventsApi.client";
import HrChangeEventTypeBadge from "./HrChangeEventTypeBadge";

export type HrChangeEventsTableProps = {
  items: HrChangeEventRow[];
  loading?: boolean;
  emptyMessage?: string;
  onRowClick?: (row: HrChangeEventRow) => void;
};

export function HrChangeEventsTable({
  items,
  loading = false,
  emptyMessage = "Изменений не найдено.",
  onRowClick,
}: HrChangeEventsTableProps) {
  if (loading) {
    return (
      <div
        data-testid="hr-change-events-loading"
        className="rounded-xl border border-zinc-200 px-4 py-8 text-center text-sm text-zinc-500 dark:border-zinc-800"
      >
        Загрузка изменений…
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div
        data-testid="hr-change-events-empty"
        className="rounded-xl border border-dashed border-zinc-300 px-4 py-10 text-center text-sm text-zinc-500 dark:border-zinc-700 dark:text-zinc-400"
      >
        {emptyMessage}
      </div>
    );
  }

  return (
    <div
      data-testid="hr-change-events-table"
      className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800"
    >
      <table className="min-w-full divide-y divide-zinc-200 text-sm dark:divide-zinc-800">
        <thead className="bg-zinc-50 dark:bg-zinc-900/50">
          <tr>
            {["Дата", "Сотрудник", "Тип", "Отделение", "Было", "Стало"].map((header) => (
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
              key={row.change_event_id}
              data-testid={`hr-change-event-row-${row.change_event_id}`}
              className={onRowClick ? "cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-900/40" : undefined}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
            >
              <td className="whitespace-nowrap px-3 py-2 text-zinc-700 dark:text-zinc-300">
                {formatHrChangeEventDate(row.event_at)}
              </td>
              <td className="px-3 py-2 text-zinc-900 dark:text-zinc-100">
                <div>{row.full_name || "—"}</div>
                {row.employee_id != null ? (
                  <div className="text-xs text-zinc-500">ID {row.employee_id}</div>
                ) : null}
              </td>
              <td className="px-3 py-2">
                <HrChangeEventTypeBadge eventType={row.event_type} />
              </td>
              <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">
                {formatHrChangeEventValue(row.department)}
              </td>
              <td className="max-w-[14rem] truncate px-3 py-2 text-zinc-600 dark:text-zinc-400">
                {formatHrChangeEventValue(row.old_value)}
              </td>
              <td className="max-w-[14rem] truncate px-3 py-2 text-zinc-800 dark:text-zinc-200">
                {formatHrChangeEventValue(row.new_value)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
