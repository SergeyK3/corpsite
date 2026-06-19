import { describe, expect, it } from "vitest";

import { displayNormalizedRecordIin, isMaskedIin } from "./normalizedRecordIin";

describe("normalizedRecordIin", () => {
  it("returns full IIN unchanged", () => {
    expect(displayNormalizedRecordIin({ iin: "851101300451" })).toBe("851101300451");
  });

  it("never renders masked placeholders", () => {
    expect(displayNormalizedRecordIin({ iin: "8511****51" })).toBe("—");
    expect(displayNormalizedRecordIin({ iin: "8511*****51" })).toBe("—");
  });

  it("returns dash when IIN is missing", () => {
    expect(displayNormalizedRecordIin({ iin: "" })).toBe("—");
    expect(displayNormalizedRecordIin(null)).toBe("—");
  });

  it("detects masked patterns", () => {
    expect(isMaskedIin("8511****51")).toBe(true);
    expect(isMaskedIin("851101300451")).toBe(false);
  });
});
