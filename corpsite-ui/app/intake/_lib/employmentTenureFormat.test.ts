import { describe, expect, it } from "vitest";

import {
  formatTenureDaysCount,
  formatTenureDecimalYears,
  formatTenureDisplay,
  formatTenureYmd,
} from "./employmentTenureFormat";

describe("employmentTenureFormat", () => {
  it("formats decimal years with comma separator", () => {
    expect(formatTenureDecimalYears(7705)).toBe("21,10");
  });

  it("formats tenure display with years and days", () => {
    expect(formatTenureDisplay(7705)).toBe("21,10 года (7 705 дней)");
  });

  it("formats day count with grouping", () => {
    expect(formatTenureDaysCount(12442)).toBe("12 442");
  });

  it("formats calendar ymd breakdown", () => {
    expect(formatTenureYmd({ years: 21, months: 1, days: 5 })).toBe("21 год 1 месяц 5 дней");
  });
});
