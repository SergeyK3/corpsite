// FILE: corpsite-ui/lib/visibilityNav.test.ts
import { describe, expect, it } from "vitest";

import type { MeInfo } from "./types";
import {
  canAccessDirectoryRoute,
  hasE1PersonnelVisibility,
  hasPersonnelVisibility,
  shouldShowOrgUnitsPanel,
} from "./visibilityNav";
import { buildVisibilityDirectoryNavItems } from "./personnelNav";

describe("visibilityNav", () => {
  const admin: MeInfo = { user_id: 1, role_id: 2 };
  const hrHead: MeInfo = { user_id: 8, role_id: 8, role_code: "HR_HEAD", has_personnel_admin: true };
  const observerWithAssignment: MeInfo = {
    user_id: 2,
    role_id: 3,
    show_org_sidebar: true,
    has_personnel_visibility: true,
    personnel_visibility: { can_view_tasks: false },
  };
  const observerPlain: MeInfo = { user_id: 3, role_id: 3 };

  it("hasPersonnelVisibility respects admin shell, HR contour, and assignment flag", () => {
    expect(hasPersonnelVisibility(admin)).toBe(true);
    expect(hasPersonnelVisibility(hrHead)).toBe(true);
    expect(hasPersonnelVisibility(observerWithAssignment)).toBe(true);
    expect(hasPersonnelVisibility(observerPlain)).toBe(false);
    expect(hasE1PersonnelVisibility(hrHead)).toBe(false);
    expect(hasE1PersonnelVisibility(observerWithAssignment)).toBe(true);
  });

  it("HR head on position cabinet gets personnel sidebar items without sysadmin extras", () => {
    const items = buildVisibilityDirectoryNavItems(hrHead);
    expect(items.map((item) => item.title)).toEqual(["Персонал", "Кадровые процессы"]);
    expect(shouldShowOrgUnitsPanel("/tasks", hrHead)).toBe(true);
    expect(canAccessDirectoryRoute("/directory/personnel/journal", hrHead)).toBe(true);
    expect(canAccessDirectoryRoute("/directory/staff", hrHead)).toBe(true);
    expect(canAccessDirectoryRoute("/admin/system", hrHead)).toBe(false);
  });

  it("shouldShowOrgUnitsPanel hides for plain observer", () => {
    expect(shouldShowOrgUnitsPanel("/directory/staff", observerPlain)).toBe(false);
    expect(shouldShowOrgUnitsPanel("/directory/staff", observerWithAssignment)).toBe(true);
  });

  it("shouldShowOrgUnitsPanel keeps org tree on position cabinet routes for visibility users", () => {
    expect(shouldShowOrgUnitsPanel("/dashboards", observerWithAssignment)).toBe(true);
    expect(shouldShowOrgUnitsPanel("/education", observerWithAssignment)).toBe(true);
    expect(shouldShowOrgUnitsPanel("/dashboards", observerPlain)).toBe(false);
  });

  it("canAccessDirectoryRoute allows staff for visibility users only", () => {
    expect(canAccessDirectoryRoute("/directory/staff", observerPlain)).toBe(false);
    expect(canAccessDirectoryRoute("/directory/staff", observerWithAssignment)).toBe(true);
    expect(canAccessDirectoryRoute("/directory/personnel/journal", observerWithAssignment)).toBe(false);
    expect(canAccessDirectoryRoute("/tasks", observerWithAssignment)).toBe(false);
  });

  it("canAccessDirectoryRoute allows position cabinet stub sections without task read access", () => {
    expect(canAccessDirectoryRoute("/dashboards", observerWithAssignment)).toBe(true);
    expect(canAccessDirectoryRoute("/education", observerWithAssignment)).toBe(true);
    expect(canAccessDirectoryRoute("/dashboards", observerPlain)).toBe(true);
  });
});
