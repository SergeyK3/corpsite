import { describe, expect, it } from "vitest";

import {
  buildCreateInitialMrdPayload,
  buildImportDataIssueSummary,
  isSuitableInitialBaselineImport,
  normalizeImportBatchPeriod,
  selectSuitableControlListImports,
} from "./importInitialBaseline";
import type { ImportBatchRow, ImportSummary } from "./importApi.client";
import {
  buildInitialBaselineReviewHref,
  resolveJournalPeriodAction,
} from "./importInitialBaselineNavigation";
import type { MonthlyReferenceSummary } from "./mrdApi.client";

function batch(partial: Partial<ImportBatchRow> & Pick<ImportBatchRow, "batch_id">): ImportBatchRow {
  return {
    import_code: `IMP-${partial.batch_id}`,
    file_name: `import-${partial.batch_id}.xlsx`,
    imported_at: partial.imported_at ?? "2026-06-15T10:00:00Z",
    status: partial.status ?? "APPLY_PENDING",
    total_rows: partial.total_rows ?? 100,
    valid_rows: partial.valid_rows ?? 98,
    error_rows: partial.error_rows ?? 0,
    ...partial,
  };
}

describe("importInitialBaselineNavigation", () => {
  it("builds initial review href without creating MRD", () => {
    expect(buildInitialBaselineReviewHref("2026-06-01")).toBe(
      "/directory/personnel/import/review?report_period=2026-06-01&mode=initial",
    );
  });

  it("routes July to June initial formation when June MRD is missing", () => {
    const action = resolveJournalPeriodAction("2026-07-01", null, new Map());
    expect(action?.href).toContain("report_period=2026-06-01");
    expect(action?.href).toContain("mode=initial");
    expect(action?.href).toContain("blocked_period=2026-07-01");
  });

  it("opens July comparison review when June baseline exists", () => {
    const june = {
      mrd_id: 11,
      report_period: "2026-06-01",
      version: 1,
      status: "ACTIVE",
      row_version: 1,
      entry_count: 10,
      forked_from_reference_id: null,
      is_active_for_period: true,
    } satisfies MonthlyReferenceSummary;
    const action = resolveJournalPeriodAction("2026-07-01", null, new Map([["2026-06-01", june]]));
    expect(action?.href).toBe("/directory/personnel/import/review?report_period=2026-07-01&mode=hr");
  });
});

describe("importInitialBaseline import selection", () => {
  it("selects latest completed June import by imported_at", () => {
    const items = selectSuitableControlListImports(
      [
        batch({ batch_id: 100, report_period: "06.2026", imported_at: "2026-06-01T10:00:00Z", status: "IN_REVIEW" }),
        batch({ batch_id: 809, report_period: "2026-06-01", imported_at: "2026-06-20T10:00:00Z" }),
        batch({ batch_id: 148, report_period: "2026-06-01", imported_at: "2026-06-18T10:00:00Z", status: "IN_REVIEW" }),
      ],
      "2026-06-01",
    );
    expect(items.map((item) => item.batch_id)).toEqual([809]);
  });

  it("does not invent a separate conversion parser contract", () => {
    expect(isSuitableInitialBaselineImport(batch({ batch_id: 1, status: "APPLY_PENDING" }))).toBe(true);
    expect(normalizeImportBatchPeriod(batch({ batch_id: 1, report_period: "06.2026" }))).toBe("2026-06");
    expect(
      buildCreateInitialMrdPayload({
        commandId: "create-initial-mrd-test",
        batchId: 809,
        reportPeriod: "2026-06-01",
        reviewedRowIds: [1, 2],
        fieldCorrections: [{ row_id: 1, field_path: "full_name", corrected_value: "Иванова" }],
      }).source_batch_id,
    ).toBe(809);
  });
});

describe("buildImportDataIssueSummary", () => {
  const summary = {
    batch_id: 809,
    total_rows: 120,
    valid_iin: 118,
    by_sheet_type: {},
    with_training: 10,
    with_certification: 10,
    missing_full_name: 1,
    missing_iin: 2,
    invalid_iin: 1,
    duplicate_iin_groups: 0,
    duplicate_iin_rows: 1,
  } satisfies ImportSummary;

  it("uses batch, summary, diagnostics and issue_codes without recomputing row totals", () => {
    const result = buildImportDataIssueSummary({
      batch: batch({ batch_id: 809, total_rows: 120, valid_rows: 115, error_rows: 5 }),
      summary,
      diagnostics: {
        batch_id: 809,
        items: [],
        totals: {
          rows_total: 120,
          employee_rows: 100,
          declaration_rows: 10,
          technical_rows: 10,
          candidates_count: 50,
        },
      },
      issueRows: [
        { row_id: 1, error_codes: ["invalid_iin_checksum"] } as never,
        { row_id: 2, error_codes: ["duplicate_iin_in_batch", "missing_department"] } as never,
        { row_id: 3, error_codes: [] } as never,
      ],
    });

    expect(result.totalRows).toBe(120);
    expect(result.rowsWithoutErrors).toBe(115);
    expect(result.rowsWithErrors).toBe(5);
    expect(result.employeesWithErrors).toBe(2);
    expect(result.issueCountsByCode).toEqual(
      expect.arrayContaining([
        { code: "missing_full_name", count: 1 },
        { code: "missing_iin", count: 2 },
        { code: "invalid_iin", count: 1 },
        { code: "duplicate_iin", count: 1 },
        { code: "invalid_iin_checksum", count: 1 },
        { code: "duplicate_iin_in_batch", count: 1 },
        { code: "missing_department", count: 1 },
      ]),
    );
    expect(result.totalIssueCount).toBe(8);
  });
});
