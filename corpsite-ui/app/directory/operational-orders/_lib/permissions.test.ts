import { describe, expect, it } from "vitest";

import { canSeeOperationalOrdersNav, canPromoteWorkspace } from "./permissions";

describe("operational orders permissions", () => {
  it("shows nav when has_operational_orders_read projection is true", () => {
    expect(canSeeOperationalOrdersNav({ has_operational_orders_read: true })).toBe(true);
    expect(canSeeOperationalOrdersNav({ operational_orders_permissions: { intake_read: true } })).toBe(false);
  });

  it("gates nav by backend projection, not HR permissions", () => {
    expect(
      canSeeOperationalOrdersNav({
        has_personnel_admin: true,
        has_operational_orders_read: false,
      }),
    ).toBe(false);
  });

  it("shows nav for privileged users", () => {
    expect(canSeeOperationalOrdersNav({ is_privileged: true })).toBe(true);
  });

  it("hides promote without permission", () => {
    expect(canPromoteWorkspace({ operational_orders_permissions: { intake_read: true } })).toBe(false);
    expect(canPromoteWorkspace({ operational_orders_permissions: { promote: true } })).toBe(true);
  });
});
