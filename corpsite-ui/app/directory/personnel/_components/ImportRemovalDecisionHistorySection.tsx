"use client";

import * as React from "react";

import ImportDiffStatusBadge from "./ImportDiffStatusBadge";
import {
  REMOVED_ENTRY_CONFIRM_REMOVAL_LABEL,
  REMOVED_ENTRY_RESTORE_LABEL,
} from "../_lib/importRemovedEntryDecisions";
import {
  removedEntrySubtitle,
  removedEntryTitle,
} from "../_lib/monthlyDiffLabels";
import { getNormalizedRecordKindLabel, type MonthlyDiffRemoval } from "../_lib/importApi.client";

const REVERT_DECISION_LABEL = "Отменить решение";

type Props = {
  variant: "restored" | "confirmed";
  items: MonthlyDiffRemoval[];
  decisionsEnabled?: boolean;
  onRevert?: (item: MonthlyDiffRemoval) => void | Promise<void>;
};

function sectionTone(variant: Props["variant"]): {
  border: string;
  bg: string;
  title: string;
  head: string;
} {
  if (variant === "restored") {
    return {
      border: "border-green-200 dark:border-green-900/50",
      bg: "bg-green-50/40 dark:bg-green-950/20",
      title: "text-green-900 dark:text-green-200",
      head: "bg-green-100/60 text-green-900 dark:bg-green-950/40 dark:text-green-200",
    };
  }
  return {
    border: "border-zinc-300 dark:border-zinc-700",
    bg: "bg-zinc-50/70 dark:bg-zinc-900/40",
    title: "text-zinc-900 dark:text-zinc-100",
    head: "bg-zinc-100 text-zinc-700 dark:bg-zinc-900 dark:text-zinc-300",
  };
}

function decisionLabel(variant: Props["variant"]): string {
  return variant === "restored" ? REMOVED_ENTRY_RESTORE_LABEL : REMOVED_ENTRY_CONFIRM_REMOVAL_LABEL;
}

export default function ImportRemovalDecisionHistorySection({
  variant,
  items,
  decisionsEnabled = false,
  onRevert,
}: Props) {
  const [pendingId, setPendingId] = React.useState<number | null>(null);
  const [submitting, setSubmitting] = React.useState(false);
  const tone = sectionTone(variant);

  if (!items.length) {
    return (
      <div
        className={`rounded-xl border px-4 py-6 text-center text-sm text-zinc-500 ${tone.border}`}
        data-testid={`removal-decision-history-empty-${variant}`}
      >
        Нет записей в этом списке.
      </div>
    );
  }

  async function handleRevert(item: MonthlyDiffRemoval) {
    if (!item.removal_id || !decisionsEnabled) {
      setPendingId(null);
      return;
    }
    setSubmitting(true);
    try {
      await onRevert?.(item);
      setPendingId(null);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section
      className={`rounded-xl border p-4 ${tone.border} ${tone.bg}`}
      data-testid={`removal-decision-history-${variant}`}
    >
      <div className="mb-3">
        <h2 className={`text-sm font-semibold ${tone.title}`}>
          {decisionLabel(variant)} ({items.length})
        </h2>
        <p className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">
          Решение можно отменить до публикации эталона — запись вернётся в очередь «Ожидают решения».
        </p>
      </div>
      <div className={`overflow-x-auto rounded-lg border bg-white dark:bg-zinc-950 ${tone.border}`}>
        <table className="min-w-full text-sm">
          <thead className={`text-left text-[11px] uppercase tracking-wide ${tone.head}`}>
            <tr>
              <th className="px-3 py-2">Diff</th>
              <th className="px-3 py-2">Тип</th>
              <th className="px-3 py-2">Запись</th>
              <th className="px-3 py-2">Детали</th>
              <th className="px-3 py-2">Решение</th>
              <th className="px-3 py-2">Действия</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr
                key={`${variant}-${item.canonical_entry_id}-${item.match_key}`}
                className="border-t border-zinc-200 align-top dark:border-zinc-800"
                data-testid={`removal-decision-history-row-${item.canonical_entry_id}`}
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
                <td className="px-3 py-2 text-xs text-zinc-600 dark:text-zinc-400">
                  <div>{decisionLabel(variant)}</div>
                  {item.decided_at ? (
                    <div className="mt-0.5 text-zinc-500">
                      {new Date(item.decided_at).toLocaleString("ru-RU", {
                        dateStyle: "short",
                        timeStyle: "short",
                      })}
                    </div>
                  ) : null}
                </td>
                <td className="px-3 py-2">
                  <button
                    type="button"
                    disabled={!decisionsEnabled || submitting}
                    onClick={() => setPendingId(item.removal_id ?? null)}
                    data-testid={`removal-decision-revert-${item.canonical_entry_id}`}
                    className="rounded-lg border border-zinc-300 px-2.5 py-1 text-xs font-medium text-zinc-700 hover:bg-zinc-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-zinc-600 dark:text-zinc-200 dark:hover:bg-zinc-900"
                  >
                    {REVERT_DECISION_LABEL}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {pendingId ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          role="dialog"
          aria-modal="true"
          data-testid="removal-decision-revert-dialog"
        >
          <div className="w-full max-w-md rounded-xl border border-zinc-200 bg-white p-4 shadow-lg dark:border-zinc-800 dark:bg-zinc-950">
            <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">{REVERT_DECISION_LABEL}</h3>
            <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
              Запись вернётся в статус «Ожидают решения». Если импорт уже перешёл в «Проверка завершена», статус
              снова станет «Ожидает проверки».
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700"
                onClick={() => setPendingId(null)}
              >
                Отмена
              </button>
              <button
                type="button"
                disabled={submitting}
                className="rounded-lg bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white dark:bg-zinc-100 dark:text-zinc-900"
                data-testid="removal-decision-revert-confirm"
                onClick={() => {
                  const item = items.find((row) => row.removal_id === pendingId);
                  if (item) void handleRevert(item);
                }}
              >
                {submitting ? "Сохранение…" : "Подтвердить"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
