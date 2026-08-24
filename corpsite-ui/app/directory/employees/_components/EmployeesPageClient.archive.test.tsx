import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import EmployeesPageClient from "./EmployeesPageClient";

const { getEmployeesMock, replaceMock } = vi.hoisted(() => ({
  getEmployeesMock: vi.fn(),
  replaceMock: vi.fn(),
}));

let currentSearchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: replaceMock }),
  usePathname: () => "/directory/employees",
  useSearchParams: () => currentSearchParams,
}));

vi.mock("@/components/OrgScopeFilter", () => ({ default: () => null }));
vi.mock("./EmployeeDrawer", () => ({ default: () => null }));
vi.mock("./EmployeeCreateDrawer", () => ({ default: () => null }));
vi.mock("./ControlListEntryDialog", () => ({ default: () => null }));
vi.mock("../_lib/api.client", () => ({
  getEmployees: getEmployeesMock,
  getPositions: vi.fn(async () => ({ items: [] })),
  getDepartments: vi.fn(async () => ({ items: [] })),
  mapApiErrorToMessage: (error: unknown) => String(error),
  createEmployee: vi.fn(),
  deleteEmployee: vi.fn(),
}));
vi.mock("../../org-units/_lib/api.client", () => ({
  getOrgUnitsTree: vi.fn(async () => ({ items: [] })),
}));

const baseProps = {
  initialFilters: { status: "all", limit: 50, offset: 0 },
  initialDepartments: [],
  initialPositions: [],
  initialEmployees: { items: [], total: 0 },
};

const allOrgParams = "org_group_id=11&org_unit_id=12&unit_id=13&orgUnitId=14&selected_org_unit_id=15&ou=16&unit=17&org_unit_name=Unit&department_id=18&position_id=19";

function replaceParams(url: string): URLSearchParams {
  return new URL(url, "http://localhost").searchParams;
}

describe("EmployeesPageClient archive filters", () => {
  beforeEach(() => {
    currentSearchParams = new URLSearchParams();
    getEmployeesMock.mockReset().mockResolvedValue({ items: [], total: 0 });
    replaceMock.mockReset();
  });

  afterEach(() => cleanup());

  it("clears all organization filters and resets pagination when inactive is selected", async () => {
    currentSearchParams = new URLSearchParams(`${allOrgParams}&status=active&offset=100&limit=25&q=archive`);
    render(<EmployeesPageClient {...baseProps} />);

    fireEvent.change(screen.getByDisplayValue("Работает"), { target: { value: "inactive" } });

    await waitFor(() => expect(replaceMock).toHaveBeenCalledTimes(1));
    const params = replaceParams(replaceMock.mock.calls[0][0]);
    for (const key of ["org_group_id", "org_unit_id", "unit_id", "orgUnitId", "selected_org_unit_id", "ou", "unit", "org_unit_name", "department_id", "position_id"]) {
      expect(params.has(key)).toBe(false);
    }
    expect(params.get("status")).toBe("inactive");
    expect(params.get("offset")).toBe("0");
  });

  it("loads the archive without organization filters", async () => {
    currentSearchParams = new URLSearchParams(`${allOrgParams}&status=inactive&offset=100`);
    render(<EmployeesPageClient {...baseProps} />);

    await waitFor(() => expect(getEmployeesMock).toHaveBeenCalled());
    expect(getEmployeesMock).toHaveBeenLastCalledWith(expect.objectContaining({
      status: "inactive",
      department_id: null,
      position_id: null,
      org_group_id: null,
      org_unit_id: null,
      include_children: false,
    }));
  });

  it("keeps organization filters for statuses other than inactive", async () => {
    currentSearchParams = new URLSearchParams("status=active&org_group_id=11&org_unit_id=12&department_id=18&position_id=19");
    render(<EmployeesPageClient {...baseProps} />);

    await waitFor(() => expect(getEmployeesMock).toHaveBeenCalled());
    expect(getEmployeesMock).toHaveBeenLastCalledWith(expect.objectContaining({
      status: "active",
      department_id: "18",
      position_id: "19",
      org_group_id: 11,
      org_unit_id: "12",
      include_children: true,
    }));
  });
});
