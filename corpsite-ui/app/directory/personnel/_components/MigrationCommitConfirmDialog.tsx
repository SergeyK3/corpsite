// PMF-4E — commit confirmation dialog.
"use client";

import {
  MIGRATION_COMMIT_CANCEL_BUTTON,
  MIGRATION_COMMIT_CONFIRM_BUTTON,
  MIGRATION_COMMIT_CONFIRM_MESSAGE,
  MIGRATION_COMMIT_CONFIRM_TITLE,
} from "../_lib/personnelMigrationHrLabels";

type MigrationCommitConfirmDialogProps = {
  open: boolean;
  committing?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
};

export default function MigrationCommitConfirmDialog({
  open,
  committing = false,
  onCancel,
  onConfirm,
}: MigrationCommitConfirmDialogProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="migration-commit-confirm-title"
        className="w-full max-w-md rounded-xl border border-zinc-200 bg-white p-5 shadow-xl dark:border-zinc-800 dark:bg-zinc-950"
        data-testid="migration-commit-confirm-dialog"
      >
        <h2
          id="migration-commit-confirm-title"
          className="text-lg font-semibold text-zinc-900 dark:text-zinc-100"
        >
          {MIGRATION_COMMIT_CONFIRM_TITLE}
        </h2>
        <p className="mt-3 text-sm text-zinc-600 dark:text-zinc-400">
          {MIGRATION_COMMIT_CONFIRM_MESSAGE}
        </p>
        <div className="mt-5 flex flex-wrap justify-end gap-2">
          <button
            type="button"
            disabled={committing}
            onClick={onCancel}
            className="rounded-lg border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-800 hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-900"
          >
            {MIGRATION_COMMIT_CANCEL_BUTTON}
          </button>
          <button
            type="button"
            disabled={committing}
            onClick={onConfirm}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {committing ? "Перенос…" : MIGRATION_COMMIT_CONFIRM_BUTTON}
          </button>
        </div>
      </div>
    </div>
  );
}
