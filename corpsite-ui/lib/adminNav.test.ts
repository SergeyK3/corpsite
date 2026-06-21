// FILE: corpsite-ui/lib/adminNav.test.ts
import { describe, expect, it } from "vitest";

import {
  canSeeAdminShell,
  canSeePersonnelIdentityOperationsNav,
  canSeePersonnelLifecycleNav,
  canSeeSysadminCabinetNav,
  isForbiddenAdminRoute,
} from "./adminNav";
import type { MeInfo } from "./types";

describe("adminNav", () => {
  const systemAdmin: MeInfo = { user_id: 1, role_id: 2 };
  const privileged: MeInfo = { user_id: 2, role_id: 3, is_privileged: true };
  const hrManager: MeInfo = { user_id: 4, role_id: 3, has_personnel_admin: true };
  const regular: MeInfo = { user_id: 3, role_id: 3 };

  it("system admin sees admin shell and sysadmin nav", () => {
    expect(canSeeAdminShell(systemAdmin)).toBe(true);
    expect(canSeeSysadminCabinetNav(systemAdmin)).toBe(true);
    expect(canSeePersonnelLifecycleNav(systemAdmin)).toBe(true);
  });

  it("env-privileged operator sees sysadmin nav but not full admin shell", () => {
    expect(canSeeAdminShell(privileged)).toBe(false);
    expect(canSeeSysadminCabinetNav(privileged)).toBe(true);
    expect(canSeePersonnelLifecycleNav(privileged)).toBe(true);
  });

  it("HR enrollment manager sees personnel lifecycle but not sysadmin cabinet", () => {
    expect(canSeeAdminShell(hrManager)).toBe(false);
    expect(canSeeSysadminCabinetNav(hrManager)).toBe(false);
    expect(canSeePersonnelLifecycleNav(hrManager)).toBe(true);
    expect(canSeePersonnelIdentityOperationsNav(hrManager)).toBe(true);
  });

  it("forbidden routes respect split access", () => {
    expect(isForbiddenAdminRoute("/admin/system", privileged)).toBe(false);
    expect(isForbiddenAdminRoute("/admin/sync", privileged)).toBe(true);
    expect(isForbiddenAdminRoute("/admin/system", regular)).toBe(true);
    expect(isForbiddenAdminRoute("/admin/system/personnel-lifecycle", hrManager)).toBe(false);
    expect(isForbiddenAdminRoute("/admin/system/personnel-identity/operations", hrManager)).toBe(false);
    expect(isForbiddenAdminRoute("/admin/system/personnel-lifecycle", regular)).toBe(true);
    expect(isForbiddenAdminRoute("/admin/system/personnel-identity/operations", regular)).toBe(true);
    expect(isForbiddenAdminRoute("/admin/system", hrManager)).toBe(true);
  });
});
