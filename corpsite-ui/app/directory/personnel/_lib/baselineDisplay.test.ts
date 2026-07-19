import { describe, expect, it } from "vitest";

import type { ControlListBaselineRow } from "./importApi.client";
import {
  formatBaselineImportLabel,
  formatBaselineProvenance,
  formatBaselinePublishPreviewSummary,
  groupBaselinesByPeriod,
  resolveEffectiveBaselineIdByPeriod,
} from "./baselineDisplay";

function row(partial: Partial<ControlListBaselineRow> & Pick<ControlListBaselineRow, "baseline_id">): ControlListBaselineRow {
  return {
    publication_origin_id: partial.publication_origin_id ?? partial.baseline_id,
    report_period: partial.report_period ?? "2026-06-01",
    published_at: partial.published_at ?? "2026-06-10T10:00:00Z",
    published_by: partial.published_by ?? 1,
    entry_count: partial.entry_count ?? 1,
    ...partial,
  };
}

describe("baselineDisplay", () => {
  it("picks latest published baseline per period", () => {
    const effective = resolveEffectiveBaselineIdByPeriod([
      row({ baseline_id: 1, report_period: "2026-06-01", published_at: "2026-06-01T10:00:00Z" }),
      row({ baseline_id: 2, report_period: "2026-06-01", published_at: "2026-06-02T10:00:00Z" }),
      row({ baseline_id: 3, report_period: "2026-07-01", published_at: "2026-07-01T10:00:00Z", deleted_at: "2026-07-02T10:00:00Z" }),
    ]);
    expect(effective.get("2026-06-01")).toBe(2);
    expect(effective.has("2026-07-01")).toBe(false);
  });

  it("groups baselines by report period descending", () => {
    const groups = groupBaselinesByPeriod([
      row({ baseline_id: 1, report_period: "2026-05-01", published_at: "2026-05-01T10:00:00Z" }),
      row({ baseline_id: 2, report_period: "2026-06-01", published_at: "2026-06-01T10:00:00Z" }),
    ]);
    expect(groups.map((group) => group.reportPeriod)).toEqual(["2026-06-01", "2026-05-01"]);
  });

  it("formats legacy import label for migrated baselines", () => {
    const label = formatBaselineImportLabel(
      row({
        baseline_id: 241,
        source_import_code: "legacy-39",
        is_legacy_import: true,
        import_display_label: "До миграции (импорт #39)",
      }),
    );
    expect(label).toBe("До миграции (импорт #39)");
  });

  it("formats provenance with file, batch and publish date", () => {
    const provenance = formatBaselineProvenance(
      row({
        baseline_id: 10,
        source_file_name: "контрольный2606.xlsx",
        linked_batch_id: 809,
        published_at: "2026-07-19T05:14:37.424Z",
      }),
    );
    expect(provenance).toContain("контрольный2606.xlsx");
    expect(provenance).toContain("импорт #809");
  });

  it("builds publish preview summary lines", () => {
    const lines = formatBaselinePublishPreviewSummary({
      batch_id: 809,
      total_excel_rows: 1855,
      roster_candidate_rows: 1075,
      roster_baseline_entries: 1064,
      normalized_baseline_entries: 0,
      normalized_approved_or_promoted: 0,
      normalized_pending_excluded: 1975,
      excluded_excel_rows: 780,
      duplicate_match_keys_merged: 11,
      baseline_entry_count: 1064,
      explanation: "test",
      publish_allowed: false,
      blockers: ["Импорт 2606-02 ещё в Review (статус IN_REVIEW)."],
    });
    expect(lines.some((line) => line.includes("1064"))).toBe(true);
    expect(lines.some((line) => line.includes("1975"))).toBe(true);
  });
});
