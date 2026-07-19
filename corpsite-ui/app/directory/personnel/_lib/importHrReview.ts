import {
  getActiveMonthlyReference,
  getMrdCreationWindow,
  listMonthlyReferenceForkSources,
  type HrReviewDifference,
  type HrReviewEmployee,
  type HrReviewResponse,
} from "./mrdApi.client";
import type { ModifyAndConfirmDifferencePayload } from "./mrdDifferenceActions";
import { collapseMrdJournalRows } from "./mrdPeriodWindow";
import type { ImportHrReviewStatusFilter } from "./importHrReviewLabels";
import { NORMALIZED_RECORD_KIND_LABELS, type NormalizedRecordKind } from "./normalizedRecordLabels";

export type ImportHrReviewSummary = {
  totalChecked: number;
  withDiscrepancies: number;
  totalDiscrepancies: number;
  fixed: number;
  remaining: number;
};

export type ResolvedImportHrReviewContext = {
  mrdId: number;
  reportPeriod: string;
};

export function mapStatusFilterToApiParams(statusFilter: ImportHrReviewStatusFilter): {
  changed_only: boolean;
  review_status?: string;
} {
  switch (statusFilter) {
    case "partial":
      return { changed_only: true, review_status: "PARTIAL" };
    case "fixed":
      return { changed_only: true, review_status: "REVIEWED" };
    case "all":
      return { changed_only: false };
    case "needs_fix":
    default:
      return { changed_only: true };
  }
}

export function filterEmployeesByStatusFilter(
  employees: HrReviewEmployee[],
  statusFilter: ImportHrReviewStatusFilter,
): HrReviewEmployee[] {
  if (statusFilter === "needs_fix") {
    return employees.filter((employee) => employee.review_status === "PENDING" || employee.review_status === "PARTIAL");
  }
  if (statusFilter === "partial") {
    return employees.filter((employee) => employee.review_status === "PARTIAL");
  }
  if (statusFilter === "fixed") {
    return employees.filter((employee) => employee.review_status === "REVIEWED");
  }
  return employees;
}

export function isDifferenceResolved(diff: HrReviewDifference): boolean {
  return diff.decision_status === "CONFIRMED";
}

export function isDifferenceAwaiting(diff: HrReviewDifference): boolean {
  return diff.decision_status === "AWAITING";
}

export function computeImportHrReviewSummary(
  review: Pick<HrReviewResponse, "department_summary">,
  employees: HrReviewEmployee[],
): ImportHrReviewSummary {
  const departmentSummary = review.department_summary;
  const totalChecked = departmentSummary?.total_employees ?? 0;
  const withDiscrepancies = departmentSummary?.with_changes ?? 0;

  let totalDiscrepancies = 0;
  let fixed = 0;
  let remaining = 0;

  for (const employee of employees) {
    for (const diff of employee.differences) {
      totalDiscrepancies += 1;
      if (isDifferenceResolved(diff)) {
        fixed += 1;
      } else if (isDifferenceAwaiting(diff)) {
        remaining += 1;
      }
    }
  }

  return {
    totalChecked,
    withDiscrepancies,
    totalDiscrepancies,
    fixed,
    remaining,
  };
}

const PROBLEM_SUMMARY_BY_ATTRIBUTE: Record<string, string> = {
  education_raw: "Образование не соответствует",
  certification_raw: "Категория не соответствует",
  rate: "Ставка не соответствует",
  part_time: "Ставка не соответствует",
  workload: "Ставка не соответствует",
  employment_type: "Ставка не соответствует",
  training_raw: "Тренинги не соответствуют",
  position_raw: "Должность не соответствует",
  degree_raw: "Учёная степень не соответствует",
  experience_raw: "Стаж не соответствует",
};

export function formatDifferenceProblemSummary(diff: Pick<HrReviewDifference, "attribute" | "field_label">): string {
  const mapped = PROBLEM_SUMMARY_BY_ATTRIBUTE[diff.attribute];
  if (mapped) return mapped;
  if (diff.field_label) return `${diff.field_label} не соответствует`;
  return "Несоответствие данных";
}

export function summarizeEmployeeProblems(employee: HrReviewEmployee, limit = 3): string[] {
  const unresolved = employee.differences.filter(isDifferenceAwaiting);
  const source = unresolved.length > 0 ? unresolved : employee.differences;
  return source.slice(0, limit).map(formatDifferenceProblemSummary);
}

export function getDifferenceSectionLabel(recordKind: string | null | undefined): string | null {
  if (!recordKind || recordKind === "roster") return null;
  const kind = recordKind as NormalizedRecordKind;
  if (kind in NORMALIZED_RECORD_KIND_LABELS) {
    return NORMALIZED_RECORD_KIND_LABELS[kind];
  }
  return recordKind;
}

export function buildCorrectedValueSavePayload(options: {
  commandId: string;
  difference: HrReviewDifference;
  correctedValue: unknown;
}): ModifyAndConfirmDifferencePayload {
  return {
    command_id: options.commandId,
    difference_id: options.difference.difference_id,
    expected_row_version: options.difference.row_version,
    corrected_new_value: options.correctedValue,
  };
}

export async function resolveImportHrReviewContext(options: {
  mrdIdParam?: string | null;
  reportPeriodParam?: string | null;
}): Promise<ResolvedImportHrReviewContext | null> {
  const rawMrdId = options.mrdIdParam?.trim();
  if (rawMrdId) {
    const mrdId = Number(rawMrdId);
    if (Number.isFinite(mrdId) && mrdId > 0) {
      return { mrdId, reportPeriod: options.reportPeriodParam?.trim() || "" };
    }
  }

  const reportPeriodParam = options.reportPeriodParam?.trim();
  if (reportPeriodParam) {
    const active = await getActiveMonthlyReference(reportPeriodParam);
    if (active.active) {
      return { mrdId: active.active.mrd_id, reportPeriod: active.active.report_period };
    }
  }

  try {
    const window = await getMrdCreationWindow();
    const currentPeriod = window.allowed_periods[1] ?? window.allowed_periods[0];
    if (currentPeriod) {
      const active = await getActiveMonthlyReference(currentPeriod);
      if (active.active) {
        return { mrdId: active.active.mrd_id, reportPeriod: active.active.report_period };
      }
    }
  } catch {
    // fall through to fork sources
  }

  const sources = await listMonthlyReferenceForkSources();
  const journalRows = collapseMrdJournalRows(sources.items, sources.active_by_period);
  const latest = journalRows[0];
  if (!latest) return null;
  return { mrdId: latest.mrd_id, reportPeriod: latest.report_period };
}
