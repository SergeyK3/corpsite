export type ImportBatchIdentity = {
  batch_id: number;
  import_code: string;
  is_legacy_import?: boolean;
};

const LEGACY_IMPORT_CODE_RE = /^legacy-/i;

/** Internal batch status codes (DB/API). Display labels are Russian-only via formatImportBatchStatus. */
export const IMPORT_BATCH_STATUS = {
  UPLOADED: "UPLOADED",
  PARSED: "PARSED",
  IN_REVIEW: "IN_REVIEW",
  APPLY_PENDING: "APPLY_PENDING",
  APPLIED: "APPLIED",
  PARTIALLY_APPLIED: "PARTIALLY_APPLIED",
  FAILED: "FAILED",
  CANCELLED: "CANCELLED",
} as const;

export function isLegacyImportCode(importCode: string | null | undefined): boolean {
  return LEGACY_IMPORT_CODE_RE.test(String(importCode || ""));
}

export function resolveImportBatchCode(batch: Pick<ImportBatchIdentity, "batch_id" | "import_code" | "is_legacy_import">): string {
  if (batch.is_legacy_import ?? isLegacyImportCode(batch.import_code)) {
    return String(batch.batch_id);
  }
  return batch.import_code;
}

export function formatImportBatchLabel(batch: ImportBatchIdentity): string {
  return `Импорт ${resolveImportBatchCode(batch)}`;
}

export function formatImportBatchNumber(batch: ImportBatchIdentity): string {
  return resolveImportBatchCode(batch);
}

export function formatImportBatchDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString("ru-RU");
  } catch {
    return value;
  }
}

export function formatImportReportPeriod(value: string | null | undefined): string {
  if (!value) return "—";
  const match = /^(\d{4})-(\d{2})-\d{2}$/.exec(value);
  if (match) {
    return `${match[2]}.${match[1]}`;
  }
  return value;
}

/** Automatic pipeline still running (upload / parse). */
export function isImportBatchProcessing(status: string | null | undefined): boolean {
  return status === IMPORT_BATCH_STATUS.UPLOADED || status === IMPORT_BATCH_STATUS.PARSED;
}

/** Stage-import finished; operator manual review is expected (not an automatic job). */
export function isImportBatchAwaitingOperatorReview(status: string | null | undefined): boolean {
  return status === IMPORT_BATCH_STATUS.IN_REVIEW;
}

/** Operator completed import review (Complete Import Review) or downstream apply states. */
export function isImportBatchReviewCompleted(status: string | null | undefined): boolean {
  return (
    status === IMPORT_BATCH_STATUS.APPLY_PENDING ||
    status === IMPORT_BATCH_STATUS.APPLIED ||
    status === IMPORT_BATCH_STATUS.PARTIALLY_APPLIED
  );
}

export function isImportBatchProcessingFailed(status: string | null | undefined): boolean {
  return status === IMPORT_BATCH_STATUS.FAILED;
}

/** Only APPLY_PENDING imports are eligible for initial baseline source selection. */
export function isImportBatchSuitableForInitialBaseline(status: string | null | undefined): boolean {
  return status === IMPORT_BATCH_STATUS.APPLY_PENDING;
}

export function formatImportBatchStatus(status: string | null | undefined): string {
  if (status === IMPORT_BATCH_STATUS.CANCELLED) return "Архивирован";
  if (isImportBatchProcessing(status)) return "Обрабатывается";
  if (isImportBatchAwaitingOperatorReview(status)) return "Ожидает проверки";
  if (status === IMPORT_BATCH_STATUS.APPLY_PENDING) return "Проверка завершена";
  if (status === IMPORT_BATCH_STATUS.APPLIED) return "Применён";
  if (status === IMPORT_BATCH_STATUS.PARTIALLY_APPLIED) return "Частично применён";
  if (isImportBatchProcessingFailed(status)) return "Ошибка обработки";
  return status || "—";
}

export type ImportBatchDropdownIdentity = ImportBatchIdentity & {
  original_filename?: string | null;
  file_name?: string | null;
  report_period?: string | null;
  report_month?: string | null;
  imported_at?: string | null;
  status?: string | null;
};

export function formatImportBatchDropdownLabel(batch: ImportBatchDropdownIdentity): string {
  const fileName = batch.original_filename || batch.file_name || "—";
  const period = formatImportReportPeriod(batch.report_period || batch.report_month);
  const uploadedAt = formatImportBatchDateTime(batch.imported_at);
  const statusLabel = batch.status ? formatImportBatchStatus(batch.status) : null;
  const base = `${formatImportBatchLabel(batch)} · ${fileName} · ${period} · загружен ${uploadedAt}`;
  return statusLabel ? `${base} · ${statusLabel}` : base;
}
