import { describe, expect, it } from "vitest";

import type { MonthlyReferenceSummary } from "./mrdApi.client";
import {
  buildWorkingJournalRows,
  collapseMrdJournalRows,
  evaluateCreateBaselineOffer,
  evaluateCreateNextPeriodOffer,
  getCreationWindowPeriods,
  nextReportPeriod,
  validateCreateTargetPeriod,
} from "./mrdPeriodWindow";

function row(partial: Partial<MonthlyReferenceSummary> & Pick<MonthlyReferenceSummary, "mrd_id">): MonthlyReferenceSummary {
  return {
    report_period: partial.report_period ?? "2026-06-01",
    version: partial.version ?? 1,
    status: partial.status ?? "ACTIVE",
    row_version: partial.row_version ?? 1,
    entry_count: partial.entry_count ?? 0,
    forked_from_reference_id: partial.forked_from_reference_id ?? null,
    is_active_for_period: partial.is_active_for_period ?? partial.status === "ACTIVE",
    ...partial,
  };
}

describe("mrdPeriodWindow", () => {
  it("returns three-month creation window", () => {
    const window = getCreationWindowPeriods(new Date(2026, 6, 19));
    expect(window).toEqual(["2026-06-01", "2026-07-01", "2026-08-01"]);
  });

  it("collapses journal to one active row per period", () => {
    const items = [
      row({ mrd_id: 1, report_period: "2026-06-01", version: 1, status: "CLOSED", is_active_for_period: false }),
      row({ mrd_id: 2, report_period: "2026-06-01", version: 2, status: "ACTIVE", is_active_for_period: true }),
    ];
    const collapsed = collapseMrdJournalRows(items, { "2026-06-01": 2 });
    expect(collapsed).toHaveLength(1);
    expect(collapsed[0]?.mrd_id).toBe(2);
  });

  it("allows creating only the immediate next month in window", () => {
    const referenceDate = new Date(2026, 6, 19);
    const offer = evaluateCreateNextPeriodOffer("2026-07-01", new Set(["2026-07-01"]), referenceDate);
    expect(offer.allowed).toBe(true);
    expect(offer.targetPeriod).toBe("2026-08-01");
  });

  it("rejects target outside creation window", () => {
    const referenceDate = new Date(2026, 6, 19);
    const target = nextReportPeriod("2026-08-01");
    const error = validateCreateTargetPeriod(
      target.slice(0, 7),
      "2026-08-01",
      new Set<string>(),
      referenceDate,
    );
    expect(error).toMatch(/допустимого окна/i);
  });

  it("builds working journal rows only for the three-month window", () => {
    const referenceDate = new Date(2026, 6, 19);
    const items = [
      row({ mrd_id: 1, report_period: "2082-03-01", entry_count: 99 }),
      row({ mrd_id: 2, report_period: "2026-07-01", entry_count: 10, is_active_for_period: true }),
    ];
    const working = buildWorkingJournalRows(items, { "2026-07-01": 2 }, referenceDate);
    expect(working.map((item) => item.reportPeriod)).toEqual(["2026-06-01", "2026-07-01", "2026-08-01"]);
    expect(working.find((item) => item.reportPeriod === "2026-07-01")?.baseline?.mrd_id).toBe(2);
    expect(working.find((item) => item.reportPeriod === "2082-03-01")).toBeUndefined();
  });

  it("offers create baseline for August from July active etalon", () => {
    const referenceDate = new Date(2026, 6, 19);
    const july = row({ mrd_id: 7, report_period: "2026-07-01", status: "ACTIVE", is_active_for_period: true });
    const byPeriod = new Map([["2026-07-01", july]]);
    const offer = evaluateCreateBaselineOffer("2026-08-01", new Set(["2026-07-01"]), byPeriod, referenceDate);
    expect(offer.allowed).toBe(true);
    expect(offer.sourceMrdId).toBe(7);
  });

  it("rejects create baseline for September", () => {
    const referenceDate = new Date(2026, 6, 19);
    const july = row({ mrd_id: 7, report_period: "2026-07-01", status: "ACTIVE", is_active_for_period: true });
    const byPeriod = new Map([["2026-07-01", july]]);
    const offer = evaluateCreateBaselineOffer("2026-09-01", new Set(), byPeriod, referenceDate);
    expect(offer.allowed).toBe(false);
  });
});
