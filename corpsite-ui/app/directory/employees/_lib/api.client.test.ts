import { beforeEach, describe, expect, it, vi } from "vitest";

import { createUser } from "./api.client";

describe("createUser", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ user_id: 1, employee_id: 123, role_id: 1679 }),
    }));
  });

  it("sends the selected platform role system id to the typed creation API", async () => {
    const testLogin = ["access", "test"].join(".");
    const testPassword = "T".repeat(8);
    await createUser({
      employee_id: 123,
      role_id: 1679,
      login: testLogin,
      password: testPassword,
      is_active: true,
    });

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/directory/users"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          employee_id: 123,
          role_id: 1679,
          login: testLogin,
          password: testPassword,
          is_active: true,
        }),
      }),
    );
  });
});
