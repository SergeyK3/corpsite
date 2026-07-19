"use client";

import ImportDiffStatusBadge from "./ImportDiffStatusBadge";
import ImportRemovedEntryActions from "./ImportRemovedEntryActions";
import {
  getRemovedEntryRecommendedStep,
  REMOVED_ENTRY_CONFIRM_REMOVAL_LABEL,
  REMOVED_ENTRY_RESTORE_LABEL,
  type RemovedEntryDecisionKind,
} from "../_lib/importRemovedEntryDecisions";
import {
  removedEntrySubtitle,
  removedEntryTitle,
} from "../_lib/monthlyDiffLabels";
import { getNormalizedRecordKindLabel, type MonthlyDiffRemoval } from "../_lib/importApi.client";

type Props = {
  items: MonthlyDiffRemoval[];
  /** When true, decisions call onDecision (requires backend API). */
  decisionsEnabled?: boolean;
  onDecision?: (item: MonthlyDiffRemoval, kind: RemovedEntryDecisionKind) => void | Promise<void>;
};

export default function ImportMonthlyDiffRemovedSection({
  items,
  decisionsEnabled = false,
  onDecision,
}: Props) {
  if (!items.length) return null;

  return (
    <section className="rounded-xl border border-red-200 bg-red-50/40 p-4 dark:border-red-900/50 dark:bg-red-950/20">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-red-900 dark:text-red-200">
            Отсутствуют в новом файле ({items.length})
          </h2>
          <p className="mt-1 text-xs text-red-800/90 dark:text-red-300/90">
            Эти записи были в каноническом эталоне, но не найдены в текущем импорте. Для каждой строки
            выберите «{REMOVED_ENTRY_RESTORE_LABEL}» или «{REMOVED_ENTRY_CONFIRM_REMOVAL_LABEL}».
          </p>
        </div>
      </div>
      <div className="overflow-x-auto rounded-lg border border-red-200/80 bg-white dark:border-red-900/40 dark:bg-zinc-950">
        <table className="min-w-full text-sm">
          <thead className="bg-red-100/60 text-left text-[11px] uppercase tracking-wide text-red-900 dark:bg-red-950/40 dark:text-red-200">
            <tr>
              <th className="px-3 py-2">Diff</th>
              <th className="px-3 py-2">Тип</th>
              <th className="px-3 py-2">Запись</th>
              <th className="px-3 py-2">Детали</th>
              <th className="min-w-[12rem] px-3 py-2">Что сделать</th>
              <th className="px-3 py-2">Действия</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr
                key={`${item.canonical_entry_id}-${item.match_key}`}
                className="border-t border-red-100 align-top dark:border-red-900/30"
                data-testid={`removed-entry-row-${item.canonical_entry_id}`}
              >
                <td className="px-3 py-2">
                  <ImportDiffStatusBadge status={item.diff_status} compact />
                </td>
                <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">
                  {item.record_kind === "roster"
                    ? "Сотрудник"
                    : getNormalizedRecordKindLabel(item.record_kind, item.record_kind)}
                </td>
                <td className="px-3 py-2 font-medium text-zinc-900 dark:text-zinc-100">
                  {removedEntryTitle(item.payload)}
                </td>
                <td className="px-3 py-2 text-zinc-600 dark:text-zinc-400">
                  {removedEntrySubtitle(item.payload, item.record_kind)}
                </td>
                <td className="px-3 py-2 text-xs leading-relaxed text-zinc-700 dark:text-zinc-300">
                  {getRemovedEntryRecommendedStep(item.record_kind)}
                </td>
                <td className="px-3 py-2">
                  <ImportRemovedEntryActions
                    item={item}
                    decisionsEnabled={decisionsEnabled}
                    onDecision={onDecision}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
