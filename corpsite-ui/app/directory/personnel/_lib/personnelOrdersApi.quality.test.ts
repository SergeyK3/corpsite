import { describe, expect, it } from "vitest";

import { buildPersonnelOrdersQueryParams, parsePersonnelOrdersFilters } from "./personnelOrdersApi.client";

describe("personnel-order record quality filter", () => {
  it("defaults the journal to working records", () => {
    expect(parsePersonnelOrdersFilters(new URLSearchParams()).record_quality).toBe("WORKING");
    expect(buildPersonnelOrdersQueryParams({ record_quality: "WORKING" }).get("record_quality")).toBe("WORKING");
  });

  it("sends technical and all scopes only when explicitly selected", () => {
    expect(buildPersonnelOrdersQueryParams({ record_quality: "TECHNICAL", employee_id: 9 }).toString()).toContain("record_quality=TECHNICAL");
    expect(parsePersonnelOrdersFilters(new URLSearchParams("record_quality=TECHNICAL")).record_quality).toBe("TECHNICAL");
    expect(parsePersonnelOrdersFilters(new URLSearchParams("record_quality=ALL")).record_quality).toBe("ALL");
  });
});
