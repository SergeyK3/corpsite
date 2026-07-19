import type { ImportBatchRow } from "./importApi.client";
import { normalizeImportBatchPeriod } from "./importInitialBaseline";

export type InitialBaselineSourceSelection = {
  report_period: string;
  source_batch_id: number;
  import_code?: string | null;
  selected_by?: number;
  selected_at?: string | null;
  updated_at?: string | null;
  lifecycle_status?: "ACTIVE" | "CONSUMED";
  consumed_at?: string | null;
  consumed_mrd_id?: number | null;
  mutable?: boolean;
};

export function reportPeriodIsoFromBatch(
  batch: Pick<ImportBatchRow, "report_period" | "report_month">,
): string | null {
  const month = normalizeImportBatchPeriod(batch);
  if (!month) return null;
  return `${month}-01`;
}

export function buildInitialBaselineSourceByPeriod(
  items: InitialBaselineSourceSelection[],
): Map<string, number> {
  const map = new Map<string, number>();
  for (const item of items) {
    if (item.mutable === false) continue;
    map.set(item.report_period.slice(0, 10), item.source_batch_id);
  }
  return map;
}

export function buildInitialBaselineSourceIndex(
  items: InitialBaselineSourceSelection[],
): Map<string, InitialBaselineSourceSelection> {
  const map = new Map<string, InitialBaselineSourceSelection>();
  for (const item of items) {
    map.set(item.report_period.slice(0, 10), item);
  }
  return map;
}

export function resolveSelectedBatchIdForPeriod(
  reportPeriodIso: string,
  sourceByPeriod: Map<string, number>,
): number | null {
  return sourceByPeriod.get(reportPeriodIso.slice(0, 10)) ?? null;
}

export function resolveInitialBaselineSourceSelectionForPeriod(
  batch: Pick<ImportBatchRow, "batch_id" | "report_period" | "report_month">,
  selectionByPeriod: Map<string, InitialBaselineSourceSelection>,
): InitialBaselineSourceSelection | null {
  const periodIso = reportPeriodIsoFromBatch(batch);
  if (!periodIso) return null;
  const selection = selectionByPeriod.get(periodIso);
  if (!selection || selection.source_batch_id !== batch.batch_id) return null;
  return selection;
}

export function isInitialBaselineSourceRow(
  row: Pick<ImportBatchRow, "batch_id" | "report_period" | "report_month">,
  sourceByPeriod: Map<string, number>,
): boolean {
  const periodIso = reportPeriodIsoFromBatch(row);
  if (!periodIso) return false;
  return sourceByPeriod.get(periodIso) === row.batch_id;
}

export function canSelectInitialBaselineSource(
  selection: InitialBaselineSourceSelection | null | undefined,
): boolean {
  return selection == null || selection.mutable !== false;
}
