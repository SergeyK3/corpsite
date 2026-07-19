import type { ControlListBaselineRow } from "../_lib/importApi.client";
import { formatImportBatchDateTime, formatImportReportPeriod } from "./importBatchDisplay";

export function formatBaselinePublishedAt(value: string | null | undefined): string {
  return formatImportBatchDateTime(value);
}

export function formatBaselineReportPeriod(value: string | null | undefined): string {
  return formatImportReportPeriod(value);
}

export function formatBaselineImportLabel(row: ControlListBaselineRow): string {
  if (row.import_display_label) return row.import_display_label;
  if (row.is_legacy_import) {
    const code = row.source_import_code || "";
    const suffix = code.startsWith("legacy-") ? code.slice("legacy-".length) : String(row.baseline_id);
    return `До миграции (импорт #${suffix})`;
  }
  return row.source_import_code || `Публикация #${row.baseline_id}`;
}

export function formatBaselineProvenance(row: ControlListBaselineRow): string {
  const parts: string[] = [];
  if (row.source_file_name) parts.push(row.source_file_name);
  const batchId = row.linked_batch_id ?? row.source_batch_id ?? row.origin_batch_id;
  if (batchId) parts.push(`импорт #${batchId}`);
  parts.push(`опубликован ${formatBaselinePublishedAt(row.published_at || row.promoted_at)}`);
  return parts.join(" · ");
}

export function isBaselineSoftDeleted(row: Pick<ControlListBaselineRow, "deleted_at">): boolean {
  return Boolean(row.deleted_at);
}

export function resolveEffectiveBaselineIdByPeriod(
  items: ControlListBaselineRow[],
): Map<string, number> {
  const best = new Map<string, { baselineId: number; publishedAt: string }>();
  for (const item of items) {
    if (isBaselineSoftDeleted(item)) continue;
    const period = item.report_period;
    if (!period) continue;
    const publishedAt = item.published_at || item.promoted_at || "";
    const current = best.get(period);
    if (!current || publishedAt >= current.publishedAt) {
      best.set(period, { baselineId: item.baseline_id, publishedAt });
    }
  }
  return new Map([...best.entries()].map(([period, value]) => [period, value.baselineId]));
}

export function groupBaselinesByPeriod(items: ControlListBaselineRow[]): Array<{
  reportPeriod: string;
  items: ControlListBaselineRow[];
}> {
  const groups = new Map<string, ControlListBaselineRow[]>();
  for (const item of items) {
    const period = item.report_period || "—";
    const bucket = groups.get(period) ?? [];
    bucket.push(item);
    groups.set(period, bucket);
  }
  return [...groups.entries()]
    .sort(([left], [right]) => right.localeCompare(left))
    .map(([reportPeriod, bucket]) => ({
      reportPeriod,
      items: [...bucket].sort((a, b) => {
        const left = a.published_at || a.promoted_at || "";
        const right = b.published_at || b.promoted_at || "";
        return right.localeCompare(left);
      }),
    }));
}

export function formatBaselineStatus(
  row: ControlListBaselineRow,
  effectiveBaselineId: number | null,
): string {
  if (isBaselineSoftDeleted(row)) return "Помечен удалённым";
  if (effectiveBaselineId === row.baseline_id) return "Эталон периода";
  return "Архивная публикация";
}

export function formatBaselinePublishPreviewSummary(preview: BaselinePublishPreview): string[] {
  return [
    `Строк Excel в импорте: ${preview.total_excel_rows}`,
    `Roster-кандидаты: ${preview.roster_candidate_rows}`,
    `Записей roster в эталоне: ${preview.roster_baseline_entries}`,
    `Нормализованных записей (утверждено/перенесено) в эталоне: ${preview.normalized_baseline_entries}`,
    `Нормализованных записей в ожидании (не войдут): ${preview.normalized_pending_excluded}`,
    `Строк Excel, исключённых из эталона: ${preview.excluded_excel_rows}`,
    `Итого записей в эталоне: ${preview.baseline_entry_count}`,
  ];
}

export type BaselinePublishPreview = {
  batch_id: number;
  import_code?: string | null;
  batch_status?: string | null;
  total_excel_rows: number;
  roster_candidate_rows: number;
  roster_baseline_entries: number;
  normalized_baseline_entries: number;
  normalized_approved_or_promoted: number;
  normalized_pending_excluded: number;
  excluded_excel_rows: number;
  duplicate_match_keys_merged: number;
  baseline_entry_count: number;
  existing_baseline_id?: number | null;
  explanation: string;
  publish_allowed: boolean;
  blockers: string[];
};

export function formatBaselinePublishBlockers(preview: BaselinePublishPreview): string[] {
  return preview.blockers ?? [];
}
