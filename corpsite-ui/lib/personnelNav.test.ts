// FILE: corpsite-ui/lib/personnelNav.test.ts
import { describe, expect, it } from "vitest";

import type { MeInfo } from "./types";
import {
  canSeeHrProcessesNav,
  canSeePersonnelDirectoryNav,
  isHrProcessesRoute,
  isPersonnelDirectoryRoute,
  resolvePersonnelRootRedirect,
} from "./personnelNav";

describe("personnelNav", () => {
  const systemAdmin: MeInfo = { user_id: 1, role_id: 2 };
  const privileged: MeInfo = { user_id: 2, role_id: 3, is_privileged: true };
  const hrManager: MeInfo = { user_id: 4, role_id: 3, has_personnel_admin: true };
  const headWithVisibility: MeInfo = {
    user_id: 5,
    role_id: 3,
    has_personnel_visibility: true,
    show_org_sidebar: true,
  };
  const directorLike: MeInfo = {
    user_id: 6,
    role_id: 3,
    has_personnel_visibility: true,
    show_org_sidebar: true,
    personnel_visibility: { organization_wide: true },
  };
  const regular: MeInfo = { user_id: 7, role_id: 3 };

  it("canSeePersonnelDirectoryNav for managers and admins", () => {
    expect(canSeePersonnelDirectoryNav(systemAdmin)).toBe(true);
    expect(canSeePersonnelDirectoryNav(headWithVisibility)).toBe(true);
    expect(canSeePersonnelDirectoryNav(directorLike)).toBe(true);
    expect(canSeePersonnelDirectoryNav(hrManager)).toBe(true);
    expect(canSeePersonnelDirectoryNav(regular)).toBe(false);
  });

  it("canSeeHrProcessesNav for HR and sysadmin only", () => {
    expect(canSeeHrProcessesNav(systemAdmin)).toBe(true);
    expect(canSeeHrProcessesNav(privileged)).toBe(true);
    expect(canSeeHrProcessesNav(hrManager)).toBe(true);
    expect(canSeeHrProcessesNav(headWithVisibility)).toBe(false);
    expect(canSeeHrProcessesNav(directorLike)).toBe(false);
    expect(canSeeHrProcessesNav(regular)).toBe(false);
  });

  it("route helpers distinguish staff vs HR processes", () => {
    expect(isPersonnelDirectoryRoute("/directory/staff")).toBe(true);
    expect(isPersonnelDirectoryRoute("/directory/staff/42")).toBe(true);
    expect(isHrProcessesRoute("/directory/personnel/journal")).toBe(true);
    expect(isHrProcessesRoute("/directory/personnel/import")).toBe(true);
    expect(isPersonnelDirectoryRoute("/directory/personnel/journal")).toBe(false);
    expect(isHrProcessesRoute("/directory/staff")).toBe(false);
  });

  it("resolvePersonnelRootRedirect sends HR to journal and managers to staff", () => {
    expect(resolvePersonnelRootRedirect(systemAdmin)).toBe("/directory/personnel/journal");
    expect(resolvePersonnelRootRedirect(privileged)).toBe("/directory/personnel/journal");
    expect(resolvePersonnelRootRedirect(hrManager)).toBe("/directory/personnel/journal");
    expect(resolvePersonnelRootRedirect(headWithVisibility)).toBe("/directory/staff");
    expect(resolvePersonnelRootRedirect(directorLike)).toBe("/directory/staff");
    expect(resolvePersonnelRootRedirect(regular)).toBe("/tasks");
  });

  it("resolvePersonnelRootRedirect prefers HR journal when user has both HR and visibility", () => {
    const hrWithVisibility: MeInfo = {
      user_id: 8,
      role_id: 3,
      has_personnel_admin: true,
      has_personnel_visibility: true,
      show_org_sidebar: true,
    };
    expect(resolvePersonnelRootRedirect(hrWithVisibility)).toBe("/directory/personnel/journal");
  });
});
