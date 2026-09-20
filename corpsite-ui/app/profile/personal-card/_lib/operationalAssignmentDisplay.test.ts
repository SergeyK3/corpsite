import { describe, expect, it } from "vitest";

import { displayEmploymentRate, displayOperationalStatus } from "./operationalAssignmentDisplay";

describe("operational assignment display", () => {
  it("localizes active without changing other canonical status values", () => {
    expect(displayOperationalStatus("active")).toBe("Работает");
    expect(displayOperationalStatus("suspended")).toBe("suspended");
    expect(displayOperationalStatus(null)).toBeNull();
  });

  it("formats a numeric employment rate with two fraction digits", () => {
    expect(displayEmploymentRate(1)).toBe("1.00");
    expect(displayEmploymentRate(0.5)).toBe("0.50");
    expect(displayEmploymentRate(null)).toBeNull();
  });
});
