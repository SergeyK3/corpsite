import { describe, expect, it } from "vitest";

import {
  buildPersonnelOrdersHref,
  parsePersonnelOrdersFilters,
} from "./personnelOrdersApi.client";

describe("personnelOrdersApi characterization", () => {
  it("defaults include_closed to false when query param absent", () => {
    expect(parsePersonnelOrdersFilters(new URLSearchParams("")).include_closed).toBe(false);
  });

  it("preserves legacy include_archived alias as include_closed", () => {
    expect(
      parsePersonnelOrdersFilters(new URLSearchParams("include_archived=true")).include_closed,
    ).toBe(true);
  });

  it("builds journal href without closed filter by default", () => {
    expect(buildPersonnelOrdersHref({})).toBe("/directory/personnel/orders");
  });
});
