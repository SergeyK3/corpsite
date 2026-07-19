import type { CompleteImportReviewBlocker } from "./importApi.client";
import type { ImportBatchRow } from "./importApi.client";

/** Primary action on normalized records review — completes row review checkpoint, not MRD/baseline. */
export const COMPLETE_NORMALIZED_REVIEW_BUTTON_LABEL = "Завершить проверку записей";

export type CompleteImportReviewResolveTarget = {
  href: string;
  label: string;
};

export function buildCompleteImportReviewResolveTarget(
  blocker: CompleteImportReviewBlocker,
): CompleteImportReviewResolveTarget {
  const batchId = blocker.batch_id;
  switch (blocker.resolve_kind) {
    case "normalized_review":
      return {
        href: `/directory/personnel/import/review?batch=${batchId}&status=pending`,
        label: "Открыть записи pending",
      };
    case "import_analytics":
      return {
        href: `/directory/personnel/import/${batchId}`,
        label: "Открыть аналитику импорта",
      };
    case "import_list":
      return {
        href: "/directory/personnel/import",
        label: "К списку импортов",
      };
    case "removed_review":
      return {
        href: `/directory/personnel/import/review?batch=${batchId}`,
        label: "Решить отсутствующие в файле",
      };
    default:
      return {
        href: `/directory/personnel/import/${batchId}`,
        label: "Открыть импорт",
      };
  }
}

export function formatCompleteImportReviewBlockerTitle(code: string): string {
  switch (code) {
    case "ERROR_ROWS":
      return "Ошибки парсинга Excel";
    case "PENDING_NORMALIZED":
      return "Не проверены normalized-записи";
    case "PENDING_REMOVED_DECISIONS":
      return "Отсутствуют в файле без решения";
    case "BATCH_STATUS":
      return "Недопустимый статус импорта";
    default:
      return "Блокер";
  }
}

export function canShowCompleteImportReview(status: string | null | undefined): boolean {
  return status === "IN_REVIEW" || status === "APPLY_PENDING" || status === "APPLIED" || status === "PARTIALLY_APPLIED";
}

export function isCompleteImportReviewDone(status: string | null | undefined): boolean {
  return status === "APPLY_PENDING" || status === "APPLIED" || status === "PARTIALLY_APPLIED";
}

export function extractCompleteReviewBlockerCounts(
  blockers: CompleteImportReviewBlocker[],
  batch?: Pick<ImportBatchRow, "error_rows"> | null,
): { pendingRecords: number; parseErrors: number; pendingRemovals: number } {
  let pendingRecords = 0;
  let parseErrors = batch?.error_rows ?? 0;
  let pendingRemovals = 0;

  for (const blocker of blockers) {
    if (blocker.code === "PENDING_NORMALIZED") {
      pendingRecords = blocker.count ?? pendingRecords;
    }
    if (blocker.code === "ERROR_ROWS") {
      parseErrors = blocker.count ?? parseErrors;
    }
    if (blocker.code === "PENDING_REMOVED_DECISIONS") {
      pendingRemovals = blocker.count ?? pendingRemovals;
    }
  }

  return { pendingRecords, parseErrors, pendingRemovals };
}

/** Operator-facing summary for disabled complete-review action. */
export function formatCompleteImportReviewBlockerSummary(
  blockers: CompleteImportReviewBlocker[],
  batch?: Pick<ImportBatchRow, "error_rows"> | null,
): string | null {
  if (!blockers.length) {
    return null;
  }

  const { pendingRecords, parseErrors, pendingRemovals } = extractCompleteReviewBlockerCounts(blockers, batch);
  const parts: string[] = [];

  if (pendingRecords > 0) {
    parts.push(`не проверено ${pendingRecords} записей`);
  }
  if (parseErrors > 0) {
    parts.push(`ошибок парсинга — ${parseErrors}`);
  }
  if (pendingRemovals > 0) {
    parts.push(`без решения «отсутствует в файле» — ${pendingRemovals}`);
  }

  if (parts.length === 0) {
    const statusBlocker = blockers.find((item) => item.code === "BATCH_STATUS");
    if (statusBlocker?.message) {
      return `Импорт ожидает проверки: ${statusBlocker.message}`;
    }
    return `Импорт ожидает проверки: ${blockers[0]?.message ?? "устраните блокеры"}`;
  }

  return `Импорт ожидает проверки: ${parts.join(", ")}.`;
}
