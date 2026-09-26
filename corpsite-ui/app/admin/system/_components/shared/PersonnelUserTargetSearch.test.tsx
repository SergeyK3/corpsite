import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import PersonnelUserTargetSearch from "./PersonnelUserTargetSearch";

const { getEmployees, getPositions, getOrgUnitsTree, apiFetchJson } = vi.hoisted(() => ({
  getEmployees: vi.fn(),
  getPositions: vi.fn(),
  getOrgUnitsTree: vi.fn(),
  apiFetchJson: vi.fn(),
}));

vi.mock("@/app/directory/employees/_lib/api.client", () => ({ getEmployees, getPositions }));
vi.mock("@/app/directory/org-units/_lib/api.client", () => ({ getOrgUnitsTree }));
vi.mock("@/lib/api", () => ({ apiFetchJson }));

async function renderSearch(onChange = vi.fn()) {
  getOrgUnitsTree.mockResolvedValue({
    items: [
      { id: "10", unit_id: 10, name: "Терапия", group_id: 1, children: [] },
      { id: "20", unit_id: 20, name: "Хирургия", group_id: 2, children: [] },
    ],
  });
  apiFetchJson.mockResolvedValue({ items: [{ group_id: 1, group_name: "Стационар" }, { group_id: 2, group_name: "Поликлиника" }] });
  getPositions.mockResolvedValue({ items: [{ position_id: 7, name: "Врач" }] });
  getEmployees.mockResolvedValue({ items: [{ id: "100", fio: "Иванова Анна", department: { name: "Терапия" }, position: { name: "Врач" }, user: { user_id: 55, login: "a.ivanova" } }], total: 1 });
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
    fireEvent.change(screen.getByLabelText("Поиск по ФИО"), { target: { value: "Иванова" } });

    await waitFor(() => expect(getEmployees).toHaveBeenLastCalledWith(expect.objectContaining({
      org_group_id: "1", org_unit_id: "10", position_id: "7", q: "Иванова",
    })));
  });

  it("shows account details and returns the existing numeric USER target id after selection", async () => {
    const onChange = await renderSearch();
    const result = await screen.findByRole("button", { name: /Иванова Анна/ });
    expect(result).toHaveTextContent("login: a.ivanova");
    expect(result).toHaveTextContent("Врач");
    expect(result).toHaveTextContent("Терапия");

    fireEvent.click(result);
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ target_type: "USER", target_id: 55 }));
  });
});
