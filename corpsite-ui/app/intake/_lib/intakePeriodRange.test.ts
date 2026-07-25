import { describe, expect, it } from "vitest";

import {
  INTAKE_PERIOD_RANGE_ERROR,
  isInvalidIntakePeriodRange,
  resolveIntakePeriodRangeError,
} from "./intakePeriodRange";

describe("intakePeriodRange", () => {
  it("flags reversed training period with full dates", () => {
    expect(resolveIntakePeriodRangeError("2024-06-01", "2024-05-10")).toBe(INTAKE_PERIOD_RANGE_ERROR);
    expect(isInvalidIntakePeriodRange("2024-06-01", "2024-05-10")).toBe(true);
  });

  it("accepts valid same-year period", () => {
    expect(resolveIntakePeriodRangeError("2024-05-10", "2024-06-01")).toBeNull();
  });

  it("normalizes RU display dates before comparing range", () => {
    expect(resolveIntakePeriodRangeError("10.07.2024", "01.06.2024")).toBe(INTAKE_PERIOD_RANGE_ERROR);
    expect(resolveIntakePeriodRangeError("10.05.2024", "01.06.2024")).toBeNull();
  });

  it("ignores incomplete dates", () => {
    expect(resolveIntakePeriodRangeError("2024", "2024-06-01")).toBeNull();
    expect(resolveIntakePeriodRangeError("2024-05-10", "")).toBeNull();
  });
});
