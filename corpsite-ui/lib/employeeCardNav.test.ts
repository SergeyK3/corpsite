import { describe, expect, it } from "vitest";

import {
  buildEmployeeCardAccessHref,
  buildEmployeeCardHref,
  buildPersonCardHref,
  buildPersonCardHrefFromLegacySearchParams,
  buildPersonalCardHref,
  buildLegacyCardQueryStringFromPageSearchParams,
  parseEmployeeCardSection,
  parseRouteEmployeeId,
  parseRoutePersonId,
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
        { returnTo: "/directory/personnel/applicants?application_id=10" },
      ),
    ).toBe(
      "/directory/personnel/persons/5/card?return_to=%2Fdirectory%2Fpersonnel%2Fapplicants%3Fapplication_id%3D10",
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

  it("buildPersonCardHref accepts person_id and builds canonical route", () => {
    expect(buildPersonCardHref(5)).toBe("/directory/personnel/persons/5/card");
    expect(buildPersonCardHref(5, { section: "history" })).toBe(
      "/directory/personnel/persons/5/card?section=history",
    );
  });

  it("preserves supported legacy query params for employee → person redirect", () => {
    const params = new URLSearchParams(
      "section=access&provisionAccount=1&return_to=%2Fdirectory%2Fstaff",
    );
    expect(buildPersonCardHrefFromLegacySearchParams(501, params)).toBe(
      "/directory/personnel/persons/501/card?section=access&provisionAccount=1&return_to=%2Fdirectory%2Fstaff",
    );
  });

  it("serializes page searchParams for compatibility redirect", () => {
    expect(
      buildLegacyCardQueryStringFromPageSearchParams({
        section: "history",
        return_to: "/directory/staff",
        ignored: "x",
      }),
    ).toBe("section=history&return_to=%2Fdirectory%2Fstaff");
  });

  it("validates route id segments", () => {
    expect(parseRoutePersonId("501")).toBe("501");
    expect(parseRouteEmployeeId("42")).toBe("42");
    expect(parseRoutePersonId("0")).toBeNull();
    expect(parseRouteEmployeeId("abc")).toBeNull();
  });
});
