import type {
  ImportBatchRow,
  ImportSummary,
  RowReviewDetail,
  SheetDiagnostics,
  StagingRow,
} from "./importApi.client";
import {
  formatImportBatchLabel,
  isImportBatchSuitableForInitialBaseline,
} from "./importBatchDisplay";

/** DB status codes eligible for initial baseline (display: «Проверка завершена»). */
export const INITIAL_BASELINE_SUITABLE_STATUSES = new Set(["APPLY_PENDING"]);

export type CreateInitialMrdPayload = {
  command_id: string;
  source_batch_id: number;
  report_period: string;
  reviewed_row_ids: number[];
  field_corrections: Array<{
    row_id: number;
    field_path: string;
    corrected_value: unknown;
  }>;
};

export function normalizeImportBatchPeriod(batch: Pick<ImportBatchRow, "report_period" | "report_month">): string | null {
  const raw = (batch.report_period || batch.report_month || "").trim();
  if (!raw) return null;
  if (/^\d{4}-\d{2}/.test(raw)) return raw.slice(0, 7);
  const dotted = /^(\d{2})\.(\d{4})$/.exec(raw);
  if (dotted) return `${dotted[2]}-${dotted[1]}`;
  return null;
}

export function isSuitableInitialBaselineImport(batch: ImportBatchRow): boolean {
  if ((batch.error_rows ?? 0) > 0) return false;
  if (!isImportBatchSuitableForInitialBaseline(batch.status)) return false;
  return true;
}

/** Latest suitable completed imports for the target calendar month. */
export function selectSuitableControlListImports(
  batches: ImportBatchRow[],
  reportPeriodIso: string,
): ImportBatchRow[] {
  const targetMonth = reportPeriodIso.slice(0, 7);
  return batches
    .filter((batch) => normalizeImportBatchPeriod(batch) === targetMonth)
    .filter(isSuitableInitialBaselineImport)
    .sort((left, right) => Date.parse(right.imported_at || "") - Date.parse(left.imported_at || ""));
}

export function describeImportBatchOption(batch: ImportBatchRow): string {
  return `${formatImportBatchLabel(batch)} · batch #${batch.batch_id} · ${batch.valid_rows}/${batch.total_rows} строк`;
}

export function buildCreateInitialMrdPayload(options: {
  commandId: string;
  batchId: number;
  reportPeriod: string;
  reviewedRowIds: number[];
  fieldCorrections: CreateInitialMrdPayload["field_corrections"];
}): CreateInitialMrdPayload {
  return {
    command_id: options.commandId,
    source_batch_id: options.batchId,
    report_period: options.reportPeriod.slice(0, 10),
    reviewed_row_ids: options.reviewedRowIds,
    field_corrections: options.fieldCorrections,
  };
}

export type InitialBaselineFieldRow = {
  key: string;
  section: string;
  label: string;
  sourceValue: string;
  normalizedValue: string;
  needsManualInput: boolean;
};

export function personMatchSummary(detail: Pick<RowReviewDetail, "employee_id">): {
  code: "matched" | "unmatched" | "unknown";
  label: string;
} {
  if (detail.employee_id) {
    return { code: "matched", label: "matched" };
  }
  return { code: "unmatched", label: "unmatched" };
}

export function collectRowIssues(row: StagingRow & { error_codes?: string[] }): string[] {
  const issues = [...(row.error_codes ?? [])];
  if (!row.full_name?.trim()) issues.push("missing_full_name");
  if (!row.iin?.trim()) issues.push("missing_iin");
  if (row.org_unit_id == null && row.department) issues.push("org_unit_unresolved");
  return [...new Set(issues)];
}

export function evaluateRowReadiness(
  row: StagingRow & { error_codes?: string[] },
  detail: RowReviewDetail | null,
): "ready" | "needs_review" | "blocked" {
  const issues = collectRowIssues(row);
  if (issues.some((code) => code.startsWith("invalid_iin") || code === "duplicate_iin" || code === "missing_full_name")) {
    return "blocked";
  }
  if (!detail?.employee_id || issues.length > 0) {
    return "needs_review";
  }
  return "ready";
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  return String(value);
}

export function buildInitialBaselineFieldRows(
  row: StagingRow,
  detail: RowReviewDetail | null,
): InitialBaselineFieldRow[] {
  const rows: InitialBaselineFieldRow[] = [
    {
      key: "full_name",
      section: "Person",
      label: "ФИО",
      sourceValue: displayValue(row.full_name),
      normalizedValue: displayValue(detail?.full_name ?? row.full_name),
      needsManualInput: !detail?.full_name?.trim(),
    },
    {
      key: "iin",
      section: "Person",
      label: "ИИН",
      sourceValue: displayValue(row.iin),
      normalizedValue: displayValue(detail?.iin ?? row.iin),
      needsManualInput: !detail?.iin?.trim(),
    },
    {
      key: "department",
      section: "Employment",
      label: "Отделение",
      sourceValue: displayValue(row.department),
      normalizedValue: displayValue(detail?.department_recoding?.org_unit_name ?? row.org_unit_name ?? row.department),
      needsManualInput: !(detail?.department_recoding?.org_unit_name || row.org_unit_name),
    },
    {
      key: "position_raw",
      section: "Employment",
      label: "Должность",
      sourceValue: displayValue(row.position_raw),
      normalizedValue: displayValue(detail?.position_raw ?? row.position_raw),
      needsManualInput: !(detail?.position_raw || row.position_raw),
    },
    {
      key: "certification_raw",
      section: "Категория",
      label: "Медицинская категория",
      sourceValue: displayValue(row.certification_raw),
      normalizedValue: displayValue(detail?.qualification_categories?.[0]?.category ?? row.latest_medical_category),
      needsManualInput: !(detail?.qualification_categories?.length || row.certification_raw),
    },
    {
      key: "training_raw",
      section: "Обучение",
      label: "Тренинги",
      sourceValue: displayValue(row.training_raw),
      normalizedValue: displayValue(detail?.training?.[0]?.title ?? row.training_raw),
      needsManualInput: !(detail?.training?.length || row.training_raw),
    },
    {
      key: "education_raw",
      section: "Образование",
      label: "Образование",
      sourceValue: displayValue(row.education_raw),
      normalizedValue: displayValue(detail?.education?.[0]?.institution ?? row.education_raw),
      needsManualInput: !(detail?.education?.length || row.education_raw),
    },
  ];

  return rows;
}

export type ImportDataIssueSummary = {
  totalRows: number;
  rowsWithoutErrors: number;
  rowsWithErrors: number;
  totalIssueCount: number;
  issueCountsByCode: Array<{ code: string; count: number }>;
  employeesWithErrors: number;
};

const SUMMARY_ISSUE_CODE_FIELDS: Array<{
  code: string;
  pickCount: (summary: ImportSummary) => number | undefined;
}> = [
  { code: "missing_full_name", pickCount: (summary) => summary.missing_full_name },
  { code: "missing_iin", pickCount: (summary) => summary.missing_iin },
  { code: "invalid_iin", pickCount: (summary) => summary.invalid_iin },
  { code: "duplicate_iin", pickCount: (summary) => summary.duplicate_iin_rows },
  { code: "technical_no_iin", pickCount: (summary) => summary.technical_no_iin_rows },
  { code: "declaration_no_iin", pickCount: (summary) => summary.declaration_no_iin_rows },
];

function issueCountsFromSummary(summary: ImportSummary): Array<{ code: string; count: number }> {
  return SUMMARY_ISSUE_CODE_FIELDS.map(({ code, pickCount }) => ({
    code,
    count: pickCount(summary) ?? 0,
  })).filter((item) => item.count > 0);
}

function issueCountsFromIssueCodes(
  rows: Array<StagingRow & { error_codes?: string[] }>,
): Array<{ code: string; count: number }> {
  const counts = new Map<string, number>();
  for (const row of rows) {
    for (const code of row.error_codes ?? []) {
      counts.set(code, (counts.get(code) ?? 0) + 1);
    }
  }
  return [...counts.entries()]
    .map(([code, count]) => ({ code, count }))
    .filter((item) => item.count > 0)
    .sort((left, right) => right.count - left.count || left.code.localeCompare(right.code));
}

function mergeIssueCounts(
  summaryIssues: Array<{ code: string; count: number }>,
  rowIssues: Array<{ code: string; count: number }>,
): Array<{ code: string; count: number }> {
  const merged = new Map<string, number>();
  for (const item of summaryIssues) {
    merged.set(item.code, item.count);
  }
  for (const item of rowIssues) {
    if (!merged.has(item.code)) {
      merged.set(item.code, item.count);
    }
  }
  return [...merged.entries()]
    .map(([code, count]) => ({ code, count }))
    .sort((left, right) => right.count - left.count || left.code.localeCompare(right.code));
}

export function countEmployeesWithIssueCodes(
  rows: Array<StagingRow & { error_codes?: string[] }>,
): number {
  return rows.filter((row) => (row.error_codes?.length ?? 0) > 0).length;
}

export function buildImportDataIssueSummary(options: {
  batch: ImportBatchRow;
  summary: ImportSummary;
  diagnostics: SheetDiagnostics;
  issueRows: Array<StagingRow & { error_codes?: string[] }>;
}): ImportDataIssueSummary {
  const totalRows =
    options.diagnostics.totals.rows_total || options.batch.total_rows || options.summary.total_rows;
  const rowsWithErrors = options.batch.error_rows ?? 0;
  const rowsWithoutErrors = options.batch.valid_rows ?? Math.max(0, totalRows - rowsWithErrors);
  const issueCountsByCode = mergeIssueCounts(
    issueCountsFromSummary(options.summary),
    issueCountsFromIssueCodes(options.issueRows),
  );
  const totalIssueCount = issueCountsByCode.reduce((sum, item) => sum + item.count, 0);

  return {
    totalRows,
    rowsWithoutErrors,
    rowsWithErrors,
    totalIssueCount,
    issueCountsByCode,
    employeesWithErrors: countEmployeesWithIssueCodes(options.issueRows),
  };
}

export type InitialBaselineSummary = {
  totalRows: number;
  validRows: number;
  errorRows: number;
  employeeRows: number;
  readyRows: number;
  needsReviewRows: number;
  blockedRows: number;
};

export function summarizeInitialBaselineRows(
  rows: StagingRow[],
  detailsByRowId: Record<number, RowReviewDetail | null>,
): InitialBaselineSummary {
  let readyRows = 0;
  let needsReviewRows = 0;
  let blockedRows = 0;

  for (const row of rows) {
    const readiness = evaluateRowReadiness(row, detailsByRowId[row.row_id] ?? null);
    if (readiness === "ready") readyRows += 1;
    else if (readiness === "blocked") blockedRows += 1;
    else needsReviewRows += 1;
  }

  return {
    totalRows: rows.length,
    validRows: rows.length,
    errorRows: 0,
    employeeRows: rows.length,
    readyRows,
    needsReviewRows,
    blockedRows,
  };
}
