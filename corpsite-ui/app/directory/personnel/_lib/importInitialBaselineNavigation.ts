import type { MonthlyReferenceSummary } from "./mrdApi.client";
import { MRD_UI } from "./mrdUiLabels";
import { buildMrdWorkspaceHref } from "./mrdWorkspaceNavigation";

export const IMPORT_REVIEW_BASE_HREF = "/directory/personnel/import/review";

export function buildInitialBaselineReviewHref(
  reportPeriod: string,
  options?: { blockedPeriod?: string | null; batchId?: number | null },
): string {
  const params = new URLSearchParams({
    report_period: reportPeriod.slice(0, 10),
    mode: "initial",
  });
  if (options?.blockedPeriod) {
    params.set("blocked_period", options.blockedPeriod.slice(0, 10));
  }
  if (options?.batchId) {
    params.set("batch_id", String(options.batchId));
  }
  return `${IMPORT_REVIEW_BASE_HREF}?${params.toString()}`;
}

export function buildImportHrReviewHref(options: { reportPeriod: string; mrdId?: number | null }): string {
  const params = new URLSearchParams({
    report_period: options.reportPeriod.slice(0, 10),
    mode: "hr",
  });
  if (options.mrdId) {
    params.set("mrd_id", String(options.mrdId));
  }
  return `${IMPORT_REVIEW_BASE_HREF}?${params.toString()}`;
}

/** Normalized records review + Complete Import Review action. */
export function buildNormalizedRecordsReviewHref(batchId?: number | null): string {
  if (batchId) {
    return `${IMPORT_REVIEW_BASE_HREF}?batch=${batchId}`;
  }
  return IMPORT_REVIEW_BASE_HREF;
}

export type JournalPeriodAction = {
  label: string;
  href: string;
  testId: string;
};

/** Action button for 06/07 rows in the baselines journal. Returns null → fall back to generic logic. */
export function resolveJournalPeriodAction(
  reportPeriod: string,
  baseline: MonthlyReferenceSummary | null,
  baselineByPeriod: Map<string, MonthlyReferenceSummary>,
  options?: { selectedSourceBatchId?: number | null },
): JournalPeriodAction | null {
  const period = reportPeriod.slice(0, 10);
  const juneBaseline = baselineByPeriod.get("2026-06-01") ?? null;
  const selectedBatchId = options?.selectedSourceBatchId ?? null;

  if (period === "2026-06-01") {
    if (baseline) {
      return {
        label: MRD_UI.workWithBaselineAction,
        href: buildMrdWorkspaceHref(baseline.mrd_id),
        testId: `journal-work-${baseline.mrd_id}`,
      };
    }
    return {
      label: MRD_UI.formInitialBaselineAction,
      href: buildInitialBaselineReviewHref(period, { batchId: selectedBatchId }),
      testId: "journal-form-initial-2026-06",
    };
  }

  if (period === "2026-07-01") {
    if (!juneBaseline) {
      return {
        label: MRD_UI.workWithBaselineAction,
        href: buildInitialBaselineReviewHref("2026-06-01", { blockedPeriod: period }),
        testId: "journal-july-blocked-until-june",
      };
    }
    if (baseline) {
      return {
        label: MRD_UI.workWithBaselineAction,
        href: buildMrdWorkspaceHref(baseline.mrd_id),
        testId: `journal-work-${baseline.mrd_id}`,
      };
    }
    return {
      label: MRD_UI.workWithBaselineAction,
      href: buildImportHrReviewHref({ reportPeriod: period }),
      testId: "journal-july-comparison-review",
    };
  }

  return null;
}
