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
    expect(shouldShowOrgUnitsPanel("/directory/personnel", observerPlain)).toBe(false);
    expect(shouldShowOrgUnitsPanel("/directory/personnel", observerWithAssignment)).toBe(true);
  });

  it("canAccessDirectoryRoute allows directory for visibility users only", () => {
    expect(canAccessDirectoryRoute("/directory/personnel", observerPlain)).toBe(false);
    expect(canAccessDirectoryRoute("/directory/personnel", observerWithAssignment)).toBe(true);
    expect(canAccessDirectoryRoute("/tasks", observerWithAssignment)).toBe(false);
  });
});
