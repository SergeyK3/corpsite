import { describe, expect, it } from "vitest";

import {
  canAccessOperationalOrdersRoute,
  canSeeOperationalOrdersNav,
  isOperationalOrdersRoute,
  OPERATIONAL_ORDERS_NAV_ITEM,
} from "./operationalOrdersNav";

describe("operationalOrdersNav", () => {
  it("gates navigation by has_operational_orders_read projection", () => {
    expect(canSeeOperationalOrdersNav(null)).toBe(false);
    expect(canSeeOperationalOrdersNav({ has_operational_orders_read: true })).toBe(true);
    expect(canSeeOperationalOrdersNav({ operational_orders_permissions: { intake_read: true } })).toBe(false);
    expect(canSeeOperationalOrdersNav({ has_personnel_admin: true })).toBe(false);
  });

  it("detects operational orders routes", () => {
    expect(isOperationalOrdersRoute("/directory/operational-orders")).toBe(true);
    expect(isOperationalOrdersRoute("/directory/operational-orders/workspaces/1")).toBe(true);
    expect(isOperationalOrdersRoute("/directory/personnel/journal")).toBe(false);
  });

  it("includes icon id on nav item", () => {
    expect(OPERATIONAL_ORDERS_NAV_ITEM.iconId).toBe("operational-orders");
  });

  it("route access matches nav visibility", () => {
    expect(canAccessOperationalOrdersRoute({ has_operational_orders_read: true })).toBe(true);
    expect(canAccessOperationalOrdersRoute({ has_personnel_admin: true })).toBe(false);
  });
});
