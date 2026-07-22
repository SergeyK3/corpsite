import { describe, expect, it } from "vitest";

import {
  detectPersonnelDatePrecision,
  formatPersonnelDate,
  formatPersonnelDateRange,
  formatPersonnelDateTime,
  parsePersonnelDateInput,
} from "./personnelDateFormat";

describe("personnelDateFormat", () => {
  it("formats day-precision fields as DD.MM.YYYY even for January 1", () => {
    expect(formatPersonnelDate("2020-01-01", { precision: "day" })).toBe("01.01.2020");
    expect(formatPersonnelDate("01.01.2020", { precision: "day" })).toBe("01.01.2020");
    expect(formatPersonnelDate("1990-05-20", { precision: "day" })).toBe("20.05.1990");
  });

  it("formats year-precision fields as YYYY regardless of storage shape", () => {
    expect(formatPersonnelDate("2018", { precision: "year" })).toBe("2018");
    expect(formatPersonnelDate("2018-01-01", { precision: "year" })).toBe("2018");
    expect(formatPersonnelDate("2018-09-15", { precision: "year" })).toBe("2018");
    expect(formatPersonnelDate("15.09.2018", { precision: "year" })).toBe("2018");
  });

  it("formats month-precision fields as MM.YYYY regardless of storage shape", () => {
    expect(formatPersonnelDate("2026-06-01", { precision: "month" })).toBe("06.2026");
    expect(formatPersonnelDate("06.2026", { precision: "month" })).toBe("06.2026");
    expect(formatPersonnelDate("2018-09-15", { precision: "month" })).toBe("09.2018");
    expect(formatPersonnelDate("2026-06", { precision: "month" })).toBe("06.2026");
  });

  it("keeps legacy auto mode value-based for backward compatibility only", () => {
    expect(detectPersonnelDatePrecision("2014-01-01")).toBe("year");
    expect(formatPersonnelDate("2014-01-01", { precision: "auto" })).toBe("2014");
  });

  it("does not use auto when explicit day precision is provided", () => {
    expect(formatPersonnelDate("2014-01-01", { precision: "day" })).toBe("01.01.2014");
  });

  it("formats datetime values deterministically", () => {
    expect(formatPersonnelDateTime("2026-07-17T14:30:00+05:00")).toBe("17.07.2026, 14:30");
  });

  it("formats year ranges using explicit field precision", () => {
    expect(formatPersonnelDateRange("2014", "2018-06-30", { precision: "year" })).toBe("2014 — 2018");
  });

  it("returns empty marker for blank values", () => {
    expect(formatPersonnelDate("", { empty: "—" })).toBe("—");
    expect(formatPersonnelDateRange("", "", { precision: "year" })).toBe("—");
  });

  it("parses year input without fake full dates", () => {
    expect(parsePersonnelDateInput("2022", "year")).toBe("2022");
    expect(parsePersonnelDateInput("15.09.2022", "year")).toBe("2022");
  });

  it("parses full date input to ISO for day precision", () => {
    expect(parsePersonnelDateInput("15.09.2018", "day")).toBe("2018-09-15");
  });
});
