"use client";

import type { EmploymentCompareRow } from "../_lib/employmentVerificationCompare";

type Props = {
  rows: EmploymentCompareRow[];
};

export default function EmploymentVerificationCompareTable({ rows }: Props) {
  return (
    <div
      className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800"
      data-testid="employment-verification-compare"
    >
      <table className="min-w-full text-sm">
        <thead className="bg-zinc-50 text-left text-zinc-600 dark:bg-zinc-900 dark:text-zinc-300">
          <tr>
            <th className="px-3 py-2 font-medium">Поле</th>
            <th className="px-3 py-2 font-medium">Текущие данные</th>
            <th className="px-3 py-2 font-medium">Предлагаемые данные</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.key}
              className={
                row.changed
                  ? "bg-amber-50/80 dark:bg-amber-950/20"
                  : "border-t border-zinc-100 dark:border-zinc-800"
              }
              data-testid={`compare-row-${row.key}`}
              data-changed={row.changed ? "true" : "false"}
            >
              <td className="px-3 py-2 font-medium text-zinc-700 dark:text-zinc-200">
                {row.label}
              </td>
              <td className="px-3 py-2 text-zinc-800 dark:text-zinc-100">{row.priorValue}</td>
              <td
                className={
                  row.changed
                    ? "px-3 py-2 font-medium text-amber-950 dark:text-amber-100"
                    : "px-3 py-2 text-zinc-800 dark:text-zinc-100"
                }
              >
                {row.revisionValue}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
