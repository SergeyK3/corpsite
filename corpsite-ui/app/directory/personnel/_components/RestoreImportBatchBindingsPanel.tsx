"use client";

import * as React from "react";

import {
  mapImportApiError,
  repairBatchEmployeeBindings,
  type RepairBatchEmployeeBindingsResult,
} from "../_lib/importApi.client";

export const RESTORE_IMPORT_BATCH_BINDINGS_LABEL = "Восстановить привязки в этом импорте";
export const RESTORE_IMPORT_BATCH_BINDINGS_HELP =
  "Повторно сопоставляет записи этого импорта с сотрудниками по ИИН и другим доступным ключам.";

export type RestoreImportBatchBindingsPanelProps = {
  batchId: number | null;
  disabled?: boolean;
  onRepaired?: (result: RepairBatchEmployeeBindingsResult) => void;
  onError?: (message: string) => void;
};

export function RestoreImportBatchBindingsPanel({
  batchId,
  disabled = false,
  onRepaired,
  onError,
}: RestoreImportBatchBindingsPanelProps) {
  const [repairing, setRepairing] = React.useState(false);

  if (!batchId) {
    return null;
  }

  async function handleRepairBindings() {
    if (!batchId) {
      return;
    }
    setRepairing(true);
    try {
      const result = await repairBatchEmployeeBindings(batchId);
      onRepaired?.(result);
    } catch (error) {
      onError?.(mapImportApiError(error));
    } finally {
      setRepairing(false);
    }
  }

  return (
    <div
      className="mb-4 rounded-xl border border-blue-200 bg-blue-50/50 px-4 py-3 dark:border-blue-900/50 dark:bg-blue-950/20"
      data-testid="restore-import-batch-bindings-panel"
    >
      <div className="flex flex-wrap items-start gap-3">
        <button
          type="button"
          data-testid="restore-import-batch-bindings-button"
          data-batch-id={batchId}
          disabled={disabled || repairing}
          onClick={handleRepairBindings}
          className="rounded-lg border border-blue-300 bg-white px-4 py-2 text-sm font-medium text-blue-900 hover:bg-blue-100 disabled:opacity-50 dark:border-blue-900 dark:bg-blue-950/40 dark:text-blue-100 dark:hover:bg-blue-950/60"
        >
          {repairing ? "Восстановление привязок…" : RESTORE_IMPORT_BATCH_BINDINGS_LABEL}
        </button>
        <p className="max-w-2xl text-sm text-blue-900/90 dark:text-blue-100/90">
          {RESTORE_IMPORT_BATCH_BINDINGS_HELP}
        </p>
      </div>
    </div>
  );
}
