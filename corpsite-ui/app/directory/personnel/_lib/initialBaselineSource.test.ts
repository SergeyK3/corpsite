import { describe, expect, it } from "vitest";

import {
  buildInitialBaselineSourceByPeriod,
  isInitialBaselineSourceRow,
  reportPeriodIsoFromBatch,
  resolveSelectedBatchIdForPeriod,
} from "./initialBaselineSource";

describe("initialBaselineSource", () => {
  it("maps selections by report period", () => {
    const map = buildInitialBaselineSourceByPeriod([
      { report_period: "2026-06-01", source_batch_id: 101 },
      { report_period: "2026-07-01", source_batch_id: 202 },
    ]);
    expect(resolveSelectedBatchIdForPeriod("2026-06-01", map)).toBe(101);
    expect(resolveSelectedBatchIdForPeriod("2026-07-01", map)).toBe(202);
  });

  it("marks only mutable active selections for journal routing", () => {
    const map = buildInitialBaselineSourceByPeriod([
      { report_period: "2026-06-01", source_batch_id: 809, mutable: true },
      { report_period: "2026-07-01", source_batch_id: 900, mutable: false, lifecycle_status: "CONSUMED" },
    ]);
    expect(map.get("2026-06-01")).toBe(809);
    expect(map.has("2026-07-01")).toBe(false);
  });

  it("marks only one batch as selected for a period", () => {
    const map = buildInitialBaselineSourceByPeriod([
      { report_period: "2026-06-01", source_batch_id: 809 },
    ]);
    const first = {
      batch_id: 808,
      report_period: "06.2026",
    };
    const second = {
      batch_id: 809,
      report_period: "06.2026",
    };
    expect(isInitialBaselineSourceRow(first, map)).toBe(false);
    expect(isInitialBaselineSourceRow(second, map)).toBe(true);
  });

  it("derives report period iso from batch metadata", () => {
    expect(reportPeriodIsoFromBatch({ report_period: "06.2026", report_month: null })).toBe("2026-06-01");
    expect(reportPeriodIsoFromBatch({ report_period: null, report_month: "2026-06-01" })).toBe("2026-06-01");
  });
});
