import { describe, expect, it } from "vitest";

import { buildInitialBaselineReviewHref, buildImportHrReviewHref, resolveJournalPeriodAction } from "./importInitialBaselineNavigation";

describe("importInitialBaselineNavigation", () => {
  it("includes selected batch in form initial baseline href", () => {
    expect(buildInitialBaselineReviewHref("2026-06-01", { batchId: 809 })).toBe(
      "/directory/personnel/import/review?report_period=2026-06-01&mode=initial&batch_id=809",
    );
  });

  it("builds HR review href with mode=hr", () => {
    expect(buildImportHrReviewHref({ reportPeriod: "2026-07-01", mrdId: 12 })).toBe(
      "/directory/personnel/import/review?report_period=2026-07-01&mode=hr&mrd_id=12",
    );
  });

  it("passes selected source batch into June journal action", () => {
    const action = resolveJournalPeriodAction(
      "2026-06-01",
      null,
      new Map(),
      { selectedSourceBatchId: 809 },
    );
    expect(action?.label).toBe("Сформировать эталон");
    expect(action?.href).toContain("batch_id=809");
  });
});
