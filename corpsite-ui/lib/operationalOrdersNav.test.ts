import { describe, expect, it } from "vitest";

import { canSeeOperationalOrdersNav } from "./operationalOrdersNav";

describe("operationalOrdersNav", () => {
  it("gates navigation by read permission", () => {
    expect(canSeeOperationalOrdersNav(null)).toBe(false);
    expect(canSeeOperationalOrdersNav({ has_operational_orders_read: true })).toBe(true);
  });
});
