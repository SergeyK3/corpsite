"use client";

import {
  formatMonthlyDiffValue,
  getMonthlyDiffFieldLabel,
  type FieldDiffEntry,
} from "../_lib/monthlyDiffLabels";

type Props = {
  fieldDiffs: Record<string, FieldDiffEntry> | null | undefined;
  recordKind?: string | null;
  title?: string;
};

export default function ImportFieldDiffPanel({
  fieldDiffs,
  recordKind,
  title = "Сравнение с каноническим эталоном",
}: Props) {
  if (!fieldDiffs || Object.keys(fieldDiffs).length === 0) {
    return null;
  }

  const rows = Object.entries(fieldDiffs).sort(([a], [b]) => a.localeCompare(b, "ru"));

  return (
    <section className="rounded-xl border border-amber-200 bg-amber-50/40 p-4 dark:border-amber-900/50 dark:bg-amber-950/20">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-amber-900 dark:text-amber-200">
        {title}
      </h2>
      <p className="mb-3 text-xs text-amber-800/90 dark:text-amber-300/90">
        Каноническое значение — последнее утверждённое состояние. Значение из файла — данные текущего
        импорта до review.
      </p>
      <div className="overflow-x-auto rounded-lg border border-amber-200/80 bg-white dark:border-amber-900/40 dark:bg-zinc-950">
        <table className="min-w-full text-sm">
          <thead className="bg-amber-100/60 text-left text-[11px] uppercase tracking-wide text-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
            <tr>
              <th className="px-3 py-2">Поле</th>
              <th className="px-3 py-2">Каноническое значение</th>
              <th className="px-3 py-2">Значение из нового файла</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([field, diff]) => (
              <tr key={field} className="border-t border-amber-100 dark:border-amber-900/30">
                <td className="px-3 py-2 font-medium text-zinc-800 dark:text-zinc-200">
                  {getMonthlyDiffFieldLabel(field, recordKind)}
                </td>
                <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">
                  {formatMonthlyDiffValue(diff.canonical)}
                </td>
                <td className="px-3 py-2 text-zinc-900 dark:text-zinc-100">
                  {formatMonthlyDiffValue(diff.incoming)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
