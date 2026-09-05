import { describe, expect, it } from "vitest";

import {
  TEST_PERSONNEL_APPROVALS_HREF,
  canSeeTestPersonnelAdmin,
  canSeeTestPersonnelApprovals,
} from "./testPersonnelDeletionNav";
import { buildPersonnelSidebarNavItems } from "./personnelNav";

describe("test personnel deletion capability navigation", () => {
  it("shows ADMIN link only for request capability", () => {
    const admin = { user_id: 1, can_request_test_personnel_deletion: true };
    const hr = { user_id: 2, can_approve_test_personnel_deletion: true };
    expect(canSeeTestPersonnelAdmin(admin)).toBe(true);
    expect(canSeeTestPersonnelAdmin(hr)).toBe(false);
    expect(canSeeTestPersonnelAdmin({
      user_id: 3,
      role_id: 2,
      role_code: "ADMIN",
      has_sysadmin_api: true,
      can_read_test_personnel_deletion_audit: true,
    })).toBe(false);
  });

  it("keeps the HR approval link out of the sidebar while gating its horizontal tab", () => {
    const admin = { user_id: 1, can_request_test_personnel_deletion: true };
    const hr = { user_id: 2, can_approve_test_personnel_deletion: true };
    expect(canSeeTestPersonnelApprovals(hr)).toBe(true);
    expect(canSeeTestPersonnelApprovals(admin)).toBe(false);
    expect(buildPersonnelSidebarNavItems(hr).some((item) => item.href === TEST_PERSONNEL_APPROVALS_HREF)).toBe(false);
    expect(buildPersonnelSidebarNavItems(admin).some((item) => item.href === TEST_PERSONNEL_APPROVALS_HREF)).toBe(false);
    expect(canSeeTestPersonnelApprovals({
      user_id: 4,
      role_id: 8,
      role_code: "HR_HEAD",
      has_hr_governance: true,
      can_read_test_personnel_deletion_audit: true,
    })).toBe(false);
  });
});
