// FILE: corpsite-ui/lib/adminNav.test.ts
import { describe, expect, it } from "vitest";

import {
  canSeeAdminShell,
  canSeeSysadminCabinetNav,
  isForbiddenAdminRoute,
} from "./adminNav";
import type { MeInfo } from "./types";

describe("adminNav", () => {
  const systemAdmin: MeInfo = { user_id: 1, role_id: 2 };
  const privileged: MeInfo = { user_id: 2, role_id: 3, is_privileged: true };
  const regular: MeInfo = { user_id: 3, role_id: 3 };

  it("system admin sees admin shell and sysadmin nav", () => {
    expect(canSeeAdminShell(systemAdmin)).toBe(true);
    expect(canSeeSysadminCabinetNav(systemAdmin)).toBe(true);
  });

  it("env-privileged operator sees sysadmin nav but not full admin shell", () => {
    expect(canSeeAdminShell(privileged)).toBe(false);
    expect(canSeeSysadminCabinetNav(privileged)).toBe(true);
  });

  it("forbidden routes respect split access", () => {
    expect(isForbiddenAdminRoute("/admin/system", privileged)).toBe(false);
    expect(isForbiddenAdminRoute("/admin/sync", privileged)).toBe(true);
    expect(isForbiddenAdminRoute("/admin/system", regular)).toBe(true);
  });
});
