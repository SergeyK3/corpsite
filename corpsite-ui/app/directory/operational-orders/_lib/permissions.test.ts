import { describe, expect, it } from "vitest";

import {
  canReviewOperationalOrderArchive,
  canSeeOperationalOrdersNav,
  canPromoteWorkspace,
} from "./permissions";

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
    expect(canReviewOperationalOrderArchive({ is_privileged: true })).toBe(false);
  });

  it("shows archive navigation for the specialized review permission", () => {
    const me = {
      has_operational_orders_read: false,
      operational_orders_permissions: { archive_review: true },
    };
    expect(canSeeOperationalOrdersNav(me)).toBe(true);
    expect(canReviewOperationalOrderArchive(me)).toBe(true);
  });

  it("uses only the effective archive-review capability for editing", () => {
    expect(canReviewOperationalOrderArchive({
      role_code: "HR_HEAD",
      has_operational_orders_read: true,
      operational_orders_permissions: { archive_review: false },
    })).toBe(false);
    expect(canReviewOperationalOrderArchive({
      role_code: "HR_reg",
      operational_orders_permissions: { archive_review: true },
    })).toBe(true);
    expect(canReviewOperationalOrderArchive({
      role_code: "ADMIN",
      operational_orders_permissions: { archive_review: true },
    })).toBe(true);
    expect(canReviewOperationalOrderArchive({
      role_code: "HR_HEAD",
      operational_orders_permissions: { archive_review: false },
      has_operational_order_archive_review: true,
    })).toBe(false);
  });

  it("hides promote without permission", () => {
    expect(canPromoteWorkspace({ operational_orders_permissions: { intake_read: true } })).toBe(false);
    expect(canPromoteWorkspace({ operational_orders_permissions: { promote: true } })).toBe(true);
  });
});
