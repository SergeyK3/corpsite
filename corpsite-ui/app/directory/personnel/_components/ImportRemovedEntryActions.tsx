"use client";

import * as React from "react";

import {
  getRemovedEntryDecisionDialogBody,
  getRemovedEntryDecisionDialogTitle,
  REMOVED_ENTRY_CONFIRM_REMOVAL_LABEL,
  REMOVED_ENTRY_DECISION_FOUNDATION_NOTE,
  REMOVED_ENTRY_RESTORE_LABEL,
  removedEntryDecisionTestId,
  type RemovedEntryDecisionKind,
} from "../_lib/importRemovedEntryDecisions";
import type { MonthlyDiffRemoval } from "../_lib/importApi.client";

type Props = {
  item: MonthlyDiffRemoval;
  /** When false, buttons open an explanatory dialog only (no persistence). */
  decisionsEnabled?: boolean;
  onDecision?: (item: MonthlyDiffRemoval, kind: RemovedEntryDecisionKind) => void | Promise<void>;
};

function actionButtonClassName(variant: "primary" | "muted"): string {
  const base =
    "inline-flex rounded-lg px-2.5 py-1 text-xs font-medium transition disabled:cursor-not-allowed disabled:opacity-60";
  if (variant === "muted") {
    return `${base} border border-zinc-300 text-zinc-700 hover:bg-zinc-50 dark:border-zinc-600 dark:text-zinc-200 dark:hover:bg-zinc-900`;
  }
  return `${base} border border-blue-300 text-blue-800 hover:bg-blue-50 dark:border-blue-800 dark:text-blue-200 dark:hover:bg-blue-950/40`;
}

export default function ImportRemovedEntryActions({
  item,
  decisionsEnabled = false,
  onDecision,
}: Props) {
  const [pendingKind, setPendingKind] = React.useState<RemovedEntryDecisionKind | null>(null);
  const [submitting, setSubmitting] = React.useState(false);

  async function handleConfirm() {
    if (!pendingKind) return;
    if (!decisionsEnabled) {
      setPendingKind(null);
      return;
    }
    setSubmitting(true);
    try {
      await onDecision?.(item, pendingKind);
      setPendingKind(null);
    } finally {
      setSubmitting(false);
    }
  }

  function openDialog(kind: RemovedEntryDecisionKind) {
    setPendingKind(kind);
  }

  return (
    <>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className={actionButtonClassName("primary")}
          onClick={() => openDialog("restore")}
          data-testid={removedEntryDecisionTestId(item, "restore")}
        >
          {REMOVED_ENTRY_RESTORE_LABEL}
        </button>
        <button
          type="button"
          className={actionButtonClassName("muted")}
          onClick={() => openDialog("confirm_removal")}
          data-testid={removedEntryDecisionTestId(item, "confirm_removal")}
        >
          {REMOVED_ENTRY_CONFIRM_REMOVAL_LABEL}
        </button>
      </div>

      {pendingKind ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="removed-entry-decision-title"
          data-testid="removed-entry-decision-dialog"
        >
          <div className="w-full max-w-md rounded-xl border border-zinc-200 bg-white p-4 shadow-lg dark:border-zinc-700 dark:bg-zinc-950">
            <h3
              id="removed-entry-decision-title"
              className="text-base font-semibold text-zinc-900 dark:text-zinc-100"
            >
              {getRemovedEntryDecisionDialogTitle(pendingKind)}
            </h3>
            <p className="mt-3 text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">
              {getRemovedEntryDecisionDialogBody(item, pendingKind)}
            </p>
            {!decisionsEnabled ? (
              <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-200">
                {REMOVED_ENTRY_DECISION_FOUNDATION_NOTE}
              </p>
            ) : null}
            <div className="mt-4 flex flex-wrap justify-end gap-2">
              <button
                type="button"
                className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm text-zinc-700 hover:bg-zinc-50 dark:border-zinc-600 dark:text-zinc-200 dark:hover:bg-zinc-900"
                onClick={() => setPendingKind(null)}
                disabled={submitting}
              >
                Отмена
              </button>
              <button
                type="button"
                className="rounded-lg border border-blue-300 bg-blue-50 px-3 py-1.5 text-sm font-medium text-blue-900 hover:bg-blue-100 disabled:opacity-60 dark:border-blue-800 dark:bg-blue-950/40 dark:text-blue-100"
                onClick={() => void handleConfirm()}
                disabled={submitting}
                data-testid="removed-entry-decision-confirm"
              >
                {decisionsEnabled ? "Сохранить решение" : "Понятно"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
