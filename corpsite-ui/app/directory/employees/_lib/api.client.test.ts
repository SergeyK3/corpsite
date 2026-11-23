import { beforeEach, describe, expect, it, vi } from "vitest";

import { createUser, exportStaffExcel } from "./api.client";

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

describe("exportStaffExcel", () => {
  it("downloads xlsx with filters and without pagination", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 200, blob: async () => new Blob(["xlsx"]) }));
    const createObjectURL = vi.fn(() => "blob:staff");
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL, revokeObjectURL: vi.fn() }));
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    await exportStaffExcel({ status: "active", q: "Иванов", org_group_id: 2, org_unit_id: 3, include_children: true, position_id: 4, department_id: 5, limit: 50, offset: 100 });
    const url = new URL(vi.mocked(fetch).mock.calls[0][0] as string, "http://localhost");
    expect(url.pathname).toContain("/directory/employees/export.xlsx");
    expect(Object.fromEntries(url.searchParams)).toEqual({ status: "active", q: "Иванов", org_group_id: "2", org_unit_id: "3", include_children: "true", position_id: "4", department_id: "5" });
    expect(click).toHaveBeenCalledTimes(1);
    expect(createObjectURL).toHaveBeenCalled();
    expect(document.querySelector("a[download]")).toBeNull();
    click.mockRestore();
  });

  it("reports an empty result", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 404 }));
    await expect(exportStaffExcel({ q: "missing" })).rejects.toThrow("Нет записей для выгрузки");
  });
});
