// FILE: corpsite-ui/lib/visibilityNav.test.ts
import { describe, expect, it } from "vitest";

import type { MeInfo } from "./types";
import {
  canAccessDirectoryRoute,
  hasPersonnelVisibility,
  shouldShowOrgUnitsPanel,
} from "./visibilityNav";

describe("visibilityNav", () => {
  const admin: MeInfo = { user_id: 1, role_id: 2 };
  const observerWithAssignment: MeInfo = {
    user_id: 2,
    role_id: 3,
    show_org_sidebar: true,
    has_personnel_visibility: true,
    personnel_visibility: { can_view_tasks: false },
  };
  const observerPlain: MeInfo = { user_id: 3, role_id: 3 };

  it("hasPersonnelVisibility respects admin shell and assignment flag", () => {
    expect(hasPersonnelVisibility(admin)).toBe(true);
    expect(hasPersonnelVisibility(observerWithAssignment)).toBe(true);
    expect(hasPersonnelVisibility(observerPlain)).toBe(false);
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
