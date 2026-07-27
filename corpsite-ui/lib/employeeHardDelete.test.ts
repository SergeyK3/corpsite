import { describe, expect, it } from "vitest";

import { canHardDeleteEmployee } from "./employeeHardDelete";
import type { MeInfo } from "./types";

describe("canHardDeleteEmployee", () => {
  it("allows canonical system admin from /auth/me", () => {
    const me: MeInfo = { user_id: 1, role_id: 2, is_system_admin: true, can_hard_delete_employee: true };
    expect(canHardDeleteEmployee(me)).toBe(true);
  });

  it("allows canonical role_id=2 when an older /auth/me omits capability flags", () => {
    const me: MeInfo = { user_id: 1, role_id: 2 };
    expect(canHardDeleteEmployee(me)).toBe(true);
  });

  it("denies sysadmin API access without canonical system admin flag", () => {
    const me: MeInfo = {
      user_id: 34,
      role_id: 68,
      is_system_admin: false,
      has_sysadmin_api: true,
      can_hard_delete_employee: false,
    };
    expect(canHardDeleteEmployee(me)).toBe(false);
  });

  it("denies when profile is not loaded", () => {
    expect(canHardDeleteEmployee(null)).toBe(false);
  });
});
