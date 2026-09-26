import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import PersonnelUserTargetSearch from "./PersonnelUserTargetSearch";

const { getEmployees, getPositions, getOrgUnitsTree, apiFetchJson, fetchAdminUsers } = vi.hoisted(() => ({
  getEmployees: vi.fn(),
  getPositions: vi.fn(),
  getOrgUnitsTree: vi.fn(),
  apiFetchJson: vi.fn(),
  fetchAdminUsers: vi.fn(),
}));

vi.mock("@/app/directory/employees/_lib/api.client", () => ({ getEmployees, getPositions }));
vi.mock("@/app/directory/org-units/_lib/api.client", () => ({ getOrgUnitsTree }));
vi.mock("@/lib/api", () => ({ apiFetchJson }));
vi.mock("../../_lib/adminSystemApi.client", async (importOriginal) => ({
  ...await importOriginal<typeof import("../../_lib/adminSystemApi.client")>(),
  fetchAdminUsers,
}));

async function renderSearch(onChange = vi.fn()) {
  getOrgUnitsTree.mockResolvedValue({
    items: [
      { id: "10", unit_id: 10, name: "Терапия", group_id: 1, children: [] },
      { id: "20", unit_id: 20, name: "Хирургия", group_id: 2, children: [] },
    ],
  });
  apiFetchJson.mockResolvedValue({ items: [{ group_id: 1, group_name: "Стационар" }, { group_id: 2, group_name: "Поликлиника" }] });
  getPositions.mockResolvedValue({ items: [{ position_id: 7, name: "Врач" }] });
  fetchAdminUsers.mockResolvedValue([{ user_id: 55, employee_id: 100, is_active: true }]);
  getEmployees.mockResolvedValue({ items: [{ id: "100", fio: "Test Employee", department: { name: "Терапия" }, position: { name: "Врач" }, user: { user_id: 55, login: "employee-user-55" } }], total: 1 });
  render(<PersonnelUserTargetSearch value={null} onChange={onChange} />);
  await screen.findAllByRole("option", { name: "Стационар" });
  await waitFor(() => expect(getEmployees).toHaveBeenCalled());
  return onChange;
}

describe("PersonnelUserTargetSearch", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("links department options to the selected group and clears an incompatible department", async () => {
    await renderSearch();
    fireEvent.change(screen.getByLabelText("Группа отделений"), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText("Отделение"), { target: { value: "10" } });
    expect((screen.getByLabelText("Отделение") as HTMLSelectElement).value).toBe("10");

    fireEvent.change(screen.getByLabelText("Группа отделений"), { target: { value: "2" } });
    await waitFor(() => expect((screen.getByLabelText("Отделение") as HTMLSelectElement).value).toBe(""));
    expect(screen.queryByRole("option", { name: /Терапия/ })).not.toBeInTheDocument();
    expect(screen.getByRole("option", { name: /Хирургия/ })).toBeInTheDocument();
  });

  it("combines the independent FIO search with personnel filters", async () => {
    await renderSearch();
    fireEvent.change(screen.getByLabelText("Группа отделений"), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText("Отделение"), { target: { value: "10" } });
    fireEvent.change(screen.getByLabelText("Должность"), { target: { value: "7" } });
    fireEvent.change(screen.getByLabelText("Поиск по логину или ФИО"), { target: { value: "Test" } });

    await waitFor(() => expect(getEmployees).toHaveBeenLastCalledWith(expect.objectContaining({
      org_group_id: "1", org_unit_id: "10", position_id: "7", q: "Test",
    })));
  });

  it("shows account details and returns the existing numeric USER target id after selection", async () => {
    const onChange = await renderSearch();
    const result = await screen.findByRole("button", { name: /Test Employee/ });
    expect(result).toHaveTextContent("login: employee-user-55");
    expect(result).toHaveTextContent("Врач");
    expect(result).toHaveTextContent("Терапия");

    fireEvent.click(result);
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ target_type: "USER", target_id: 55 }));
  });

  it("finds a technical current user from the complete /admin/users response regardless of login case or personnel filters", async () => {
    const onChange = await renderSearch();
    fetchAdminUsers.mockResolvedValue([
      {
        user_id: 55, employee_id: 100, full_name: "Test Employee", login: "employee-user-55", role_id: 7, role_name: "Employee role", unit_id: 10,
        is_active: true, must_change_password: false, locked_at: null, locked_reason: null, token_version: 1, created_at: "2026-01-01T00:00:00+00:00",
      },
      {
        user_id: 99, employee_id: 0, full_name: null, login: "Admin", role_id: 1, role_name: "System administrator", unit_id: null,
        is_active: true, must_change_password: false, locked_at: null, locked_reason: null, token_version: 4, created_at: "2026-01-01T00:00:00+00:00",
      },
    ]);
    getEmployees.mockResolvedValue({ items: [], total: 0 });

    fireEvent.change(screen.getByLabelText("Группа отделений"), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText("Поиск по логину или ФИО"), { target: { value: "admin" } });
    const result = await screen.findByRole("button", { name: /Admin/ });
    expect(result).toHaveTextContent("System administrator");

    fireEvent.click(result);
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ target_type: "USER", target_id: 99 }));
  });
});
