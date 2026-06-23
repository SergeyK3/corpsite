// FILE: corpsite-ui/lib/adminNav.test.ts
import { describe, expect, it } from "vitest";

import {
  canSeeAdminShell,
  canSeePersonnelIdentityOperationsNav,
  canSeePersonnelLifecycleNav,
  canSeeRegularTaskRunsJournal,
  canSeeSysadminCabinetNav,
  isForbiddenAdminRoute,
} from "./adminNav";
import type { MeInfo } from "./types";

describe("adminNav", () => {
  const systemAdmin: MeInfo = { user_id: 1, role_id: 2, has_sysadmin_api: true };
  const directoryPrivileged: MeInfo = { user_id: 2, role_id: 3, is_privileged: true };
  const breakGlassSysadmin: MeInfo = {
    user_id: 5,
    role_id: 3,
    is_privileged: true,
    has_sysadmin_api: true,
  };
  const hrManager: MeInfo = { user_id: 4, role_id: 3, has_personnel_admin: true };
  const regular: MeInfo = { user_id: 3, role_id: 3 };

  it("system admin sees admin shell and sysadmin nav", () => {
    expect(canSeeAdminShell(systemAdmin)).toBe(true);
    expect(canSeeSysadminCabinetNav(systemAdmin)).toBe(true);
    expect(canSeePersonnelLifecycleNav(systemAdmin)).toBe(true);
    expect(canSeeRegularTaskRunsJournal(systemAdmin)).toBe(true);
  });

  it("directory-privileged role without sysadmin API sees run journal but not sysadmin nav", () => {
    expect(canSeeAdminShell(directoryPrivileged)).toBe(false);
    expect(canSeeSysadminCabinetNav(directoryPrivileged)).toBe(false);
    expect(canSeePersonnelLifecycleNav(directoryPrivileged)).toBe(false);
    expect(canSeeRegularTaskRunsJournal(directoryPrivileged)).toBe(true);
  });

  it("break-glass sysadmin user sees sysadmin nav but not full admin shell", () => {
    expect(canSeeAdminShell(breakGlassSysadmin)).toBe(false);
    expect(canSeeSysadminCabinetNav(breakGlassSysadmin)).toBe(true);
    expect(canSeePersonnelLifecycleNav(breakGlassSysadmin)).toBe(true);
    expect(canSeeRegularTaskRunsJournal(breakGlassSysadmin)).toBe(true);
  });

  it("HR enrollment manager sees personnel lifecycle but not sysadmin cabinet", () => {
    expect(canSeeAdminShell(hrManager)).toBe(false);
    expect(canSeeSysadminCabinetNav(hrManager)).toBe(false);
    expect(canSeePersonnelLifecycleNav(hrManager)).toBe(true);
    expect(canSeePersonnelIdentityOperationsNav(hrManager)).toBe(true);
    expect(canSeeRegularTaskRunsJournal(hrManager)).toBe(false);
  });

  it("regular employee cannot access run journal routes", () => {
    expect(canSeeRegularTaskRunsJournal(regular)).toBe(false);
    expect(isForbiddenAdminRoute("/regular-task-runs", regular)).toBe(true);
    expect(isForbiddenAdminRoute("/regular-task-runs", systemAdmin)).toBe(false);
    expect(isForbiddenAdminRoute("/regular-task-runs", directoryPrivileged)).toBe(false);
  });

  it("forbidden routes respect split access", () => {
    expect(isForbiddenAdminRoute("/admin/system", directoryPrivileged)).toBe(true);
    expect(isForbiddenAdminRoute("/admin/system", breakGlassSysadmin)).toBe(false);
    expect(isForbiddenAdminRoute("/admin/sync", directoryPrivileged)).toBe(true);
    expect(isForbiddenAdminRoute("/admin/system", regular)).toBe(true);
    expect(isForbiddenAdminRoute("/admin/system/personnel-lifecycle", hrManager)).toBe(false);
    expect(isForbiddenAdminRoute("/admin/system/personnel-identity/operations", hrManager)).toBe(false);
    expect(isForbiddenAdminRoute("/admin/system/personnel-lifecycle", regular)).toBe(true);
    expect(isForbiddenAdminRoute("/admin/system/personnel-identity/operations", regular)).toBe(true);
    expect(isForbiddenAdminRoute("/admin/system", hrManager)).toBe(true);
  });

  const headWithVisibility: MeInfo = {
    user_id: 10,
    role_id: 3,
    has_personnel_visibility: true,
    show_org_sidebar: true,
  };

  it("personnel vs HR processes route guards", () => {
    expect(isForbiddenAdminRoute("/directory/staff", headWithVisibility)).toBe(false);
    expect(isForbiddenAdminRoute("/directory/personnel/journal", headWithVisibility)).toBe(true);
    expect(isForbiddenAdminRoute("/directory/personnel/import", headWithVisibility)).toBe(true);
    expect(isForbiddenAdminRoute("/directory/personnel/journal", hrManager)).toBe(false);
    expect(isForbiddenAdminRoute("/directory/staff", hrManager)).toBe(false);
    expect(isForbiddenAdminRoute("/directory/personnel/journal", systemAdmin)).toBe(false);
    expect(isForbiddenAdminRoute("/directory/staff", systemAdmin)).toBe(false);
  });
});
