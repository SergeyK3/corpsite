import { describe, expect, it } from "vitest";

import type { MonthlyReferenceSummary } from "./mrdApi.client";
import {
  buildMrdCreateWizardHref,
  parseMrdCreateWizardSearchParams,
  resolveInitialCreateWizardState,
} from "./mrdForkNavigation";

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

describe("mrdForkNavigation", () => {
  it("builds create link with source and target", () => {
    expect(
      buildMrdCreateWizardHref({ sourceMrdId: 42, targetPeriod: "2026-08-01" }),
    ).toBe("/directory/personnel/monthly-references/fork?source_mrd_id=42&target_period=2026-08-01");
  });

  it("parses create wizard params", () => {
    const params = new URLSearchParams("source_mrd_id=7&target_period=2026-08-01");
    expect(parseMrdCreateWizardSearchParams(params)).toEqual({
      sourceMrdId: 7,
      targetPeriod: "2026-08-01",
    });
  });

  it("resolves initial source from url", () => {
    const items = [row({ mrd_id: 10 }), row({ mrd_id: 11, report_period: "2026-07-01" })];
    const parsed = parseMrdCreateWizardSearchParams(new URLSearchParams("source_mrd_id=10&target_period=2026-08-01"));
    expect(resolveInitialCreateWizardState(items, { "2026-06-01": 10 }, parsed)).toEqual({
      sourceMrdId: "10",
      targetPeriod: "2026-08-01",
    });
  });
});
