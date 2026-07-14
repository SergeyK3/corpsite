import { describe, expect, it } from "vitest";

import {
  buildEmployeeCardAccessHref,
  buildEmployeeCardHref,
  parseEmployeeCardSection,
} from "./employeeCardNav";

describe("employeeCardNav", () => {
  it("builds default card href", () => {
    expect(buildEmployeeCardHref(42)).toBe("/directory/personnel/employees/42/card");
  });

  it("builds section and provisioning query params", () => {
    expect(buildEmployeeCardHref(42, { section: "history" })).toBe(
      "/directory/personnel/employees/42/card?section=history",
    );
    expect(buildEmployeeCardAccessHref(42)).toBe(
      "/directory/personnel/employees/42/card?section=access&provisionAccount=1",
    );
  });

  it("parses known section ids with assignment fallback", () => {
    expect(parseEmployeeCardSection("history")).toBe("history");
    expect(parseEmployeeCardSection("unknown")).toBe("assignment");
  });
});
