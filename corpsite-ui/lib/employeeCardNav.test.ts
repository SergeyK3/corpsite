import { describe, expect, it } from "vitest";

import {
  buildEmployeeCardAccessHref,
  buildEmployeeCardHref,
  buildPersonalCardHref,
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

  it("builds personal card href with return_to", () => {
    expect(
      buildPersonalCardHref(
        { personId: 5 },
        { returnTo: "/directory/personnel-applications?application_id=10" },
      ),
    ).toBe(
      "/directory/personnel/persons/5/card?return_to=%2Fdirectory%2Fpersonnel-applications%3Fapplication_id%3D10",
    );
  });

  it("parses known section ids with assignment fallback", () => {
    expect(parseEmployeeCardSection("history")).toBe("history");
    expect(parseEmployeeCardSection("onboarding")).toBe("onboarding");
    expect(parseEmployeeCardSection("unknown")).toBe("assignment");
  });

  it("builds onboarding section href", () => {
    expect(buildEmployeeCardHref(42, { section: "onboarding" })).toBe(
      "/directory/personnel/employees/42/card?section=onboarding",
    );
  });
});
