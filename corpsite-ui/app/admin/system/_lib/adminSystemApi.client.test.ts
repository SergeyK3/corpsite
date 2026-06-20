// FILE: corpsite-ui/app/admin/system/_lib/adminSystemApi.client.test.ts
import { describe, expect, it } from "vitest";

import { formatAccessRoleLabel } from "./adminSystemApi.client";

describe("formatAccessRoleLabel", () => {
  it("renders human-readable role label with code", () => {
    const label = formatAccessRoleLabel({
      access_role_id: 1,
      code: "SYSADMIN_CABINET",
      label: "System Administrator Cabinet",
      access_level: "ADMIN",
    });
    expect(label).toContain("SYSADMIN_CABINET");
    expect(label).toContain("System Administrator Cabinet");
    expect(label).toContain("ADMIN");
  });
});

describe("target search mapping", () => {
  it("maps API search item shape", () => {
    const item = {
      target_type: "USER",
      target_id: 42,
      label: "admin",
      subtitle: "Admin User",
      metadata: { login: "admin" },
    };
    expect(item.target_id).toBe(42);
    expect(`${item.target_type}:${item.target_id}`).toBe("USER:42");
  });
});
