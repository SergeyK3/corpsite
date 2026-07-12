import { describe, expect, it } from "vitest";

import { canSeeOperationalOrdersNav, canPromoteWorkspace } from "./permissions";

describe("operational orders permissions", () => {
  it("shows nav when intake read permission present", () => {
    expect(
      canSeeOperationalOrdersNav({
        operational_orders_permissions: { intake_read: true },
      }),
    ).toBe(true);
  });

  it("hides promote without permission", () => {
    expect(canPromoteWorkspace({ operational_orders_permissions: { intake_read: true } })).toBe(false);
    expect(canPromoteWorkspace({ operational_orders_permissions: { promote: true } })).toBe(true);
  });
});
