import { describe, expect, it } from "vitest";

import {
  buildForkVersionWarnings,
  formatEtalonPeriodTitle,
  formatMrdJournalStatusLabel,
  formatMrdReportPeriod,
  validateForkPeriodTarget,
} from "./mrdDisplay";

describe("mrdDisplay", () => {
  it("formats etalon title with Russian month", () => {
    expect(formatEtalonPeriodTitle("2026-07-01")).toBe("Эталон кадровых данных за июль 2026");
  });

  it("formats report period as MM.YYYY", () => {
    expect(formatMrdReportPeriod("2026-06-01")).toBe("06.2026");
  });

  it("rejects duplicate fork period target", () => {
    const existing = new Set(["2026-07-01"]);
    expect(validateForkPeriodTarget("2026-07", existing)).toMatch(/уже существует/i);
  });

  it("formats journal status labels", () => {
    expect(formatMrdJournalStatusLabel({ status: "ACTIVE", is_active_for_period: true })).toBe("Действующий");
    expect(formatMrdJournalStatusLabel({ status: "CLOSED", is_active_for_period: false })).toBe("Архивный");
  });

  it("warns when fork version closes different active", () => {
    const warnings = buildForkVersionWarnings(
      {
        mrd_id: 1,
        report_period: "2026-06-01",
        version: 1,
        status: "CLOSED",
        row_version: 1,
        entry_count: 1,
        forked_from_reference_id: null,
        is_active_for_period: false,
      },
      {
        mrd_id: 2,
        report_period: "2026-06-01",
        version: 2,
        status: "ACTIVE",
        row_version: 3,
        entry_count: 2,
        forked_from_reference_id: 1,
        is_active_for_period: true,
      },
    );
    expect(warnings.some((line) => line.includes("действует"))).toBe(true);
  });
});
