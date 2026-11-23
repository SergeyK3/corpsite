import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import EmployeesPageClient from "./EmployeesPageClient";

const { getEmployees, exportStaffExcel, replace } = vi.hoisted(() => ({
  getEmployees: vi.fn(), exportStaffExcel: vi.fn(), replace: vi.fn(),
}));
let params = new URLSearchParams();
let pathname = "/directory/staff";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace }),
  usePathname: () => pathname,
  useSearchParams: () => params,
}));
vi.mock("@/components/OrgScopeFilter", () => ({ default: () => null }));
vi.mock("./EmployeeDrawer", () => ({ default: () => null }));
vi.mock("./EmployeeCreateDrawer", () => ({ default: () => null }));
vi.mock("./ControlListEntryDialog", () => ({ default: () => null }));
vi.mock("../_lib/api.client", () => ({
  getEmployees, exportStaffExcel,
  getPositions: vi.fn(async () => ({ items: [] })),
  getDepartments: vi.fn(async () => ({ items: [] })),
  mapApiErrorToMessage: String,
}));
vi.mock("../../org-units/_lib/api.client", () => ({ getOrgUnitsTree: vi.fn(async () => ({ items: [] })) }));
const props = {
  readOnly: true, managementView: true,
  initialFilters: {}, initialDepartments: [], initialPositions: [],
  initialEmployees: { items: [], total: 0 },
};
beforeEach(() => {
  pathname = "/directory/staff";
  params = new URLSearchParams();
  getEmployees.mockReset().mockResolvedValue({ items: [{ id: "1", fio: "Иванов" }], total: 231 });
  exportStaffExcel.mockReset().mockResolvedValue(undefined);
  replace.mockReset();
});
afterEach(cleanup);

it.each(["/directory/staff", "/directory/staff/"])("shows export on the staff roster: %s", async (route) => {
  pathname = route;
  render(<EmployeesPageClient {...props} />);
  await waitFor(() => expect(screen.getByRole("button", { name: "Выгрузить в Excel" })).toBeEnabled());
});

it.each(["/directory/employees", "/directory/personnel", "/directory/staffing", "/directory/staff/archive"])("does not add staff export to another route: %s", async (route) => {
  pathname = route;
  render(<EmployeesPageClient {...props} />);
  await waitFor(() => expect(getEmployees).toHaveBeenCalled());
  expect(screen.queryByRole("button", { name: "Выгрузить в Excel" })).not.toBeInTheDocument();
  expect(exportStaffExcel).not.toHaveBeenCalled();
});

it("uses updated applied filters after navigation without exporting the visible page", async () => {
  const { rerender } = render(<EmployeesPageClient {...props} />);
  await waitFor(() => expect(screen.getByRole("button", { name: "Выгрузить в Excel" })).toBeEnabled());
  params = new URLSearchParams("status=active&q=Петров&org_group_id=2&org_unit_id=3&department_id=5&position_id=4&limit=25&offset=100");
  rerender(<EmployeesPageClient {...props} />);
  await waitFor(() => expect(getEmployees).toHaveBeenLastCalledWith(expect.objectContaining({ q: "Петров", limit: "25", offset: "100" })));
  await waitFor(() => expect(screen.getByRole("button", { name: "Выгрузить в Excel" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "Выгрузить в Excel" }));
  await waitFor(() => expect(exportStaffExcel).toHaveBeenCalledExactlyOnceWith({
    status: "active", q: "Петров", org_group_id: 2, org_unit_id: "3",
    department_id: "5", position_id: "4", include_children: true, include_applicants: false,
  }));
});

it("disables export until the filtered roster is loaded", async () => {
  getEmployees.mockImplementation(() => new Promise(() => {}));
  render(<EmployeesPageClient {...props} />);
  const button = screen.getByRole("button", { name: "Выгрузить в Excel" });
  expect(button).toBeDisabled();
  fireEvent.click(button);
  expect(exportStaffExcel).not.toHaveBeenCalled();
});

it("exports the submitted search while preserving other applied filters", async () => {
  params = new URLSearchParams("status=active&position_id=4&offset=50");
  const { rerender } = render(<EmployeesPageClient {...props} />);
  await waitFor(() => expect(screen.getByRole("button", { name: "Выгрузить в Excel" })).toBeEnabled());
  fireEvent.change(screen.getByPlaceholderText("Поиск по ФИО или табельному номеру"), { target: { value: "12345" } });
  fireEvent.click(screen.getByRole("button", { name: "Найти" }));
  await waitFor(() => expect(replace).toHaveBeenCalled());
  params = new URL(replace.mock.calls.at(-1)![0], "http://localhost").searchParams;
  expect(params.get("q")).toBe("12345");
  expect(params.get("position_id")).toBe("4");
  expect(params.get("offset")).toBe("0");
  rerender(<EmployeesPageClient {...props} />);
  await waitFor(() => expect(getEmployees).toHaveBeenLastCalledWith(expect.objectContaining({ q: "12345", position_id: "4" })));
  await waitFor(() => expect(screen.getByRole("button", { name: "Выгрузить в Excel" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "Выгрузить в Excel" }));
  await waitFor(() => expect(exportStaffExcel).toHaveBeenCalledWith(expect.objectContaining({ q: "12345", status: "active", position_id: "4" })));
});

it("does not export when reading the roster is forbidden", async () => {
  getEmployees.mockRejectedValue(new Error("HTTP 403"));
  render(<EmployeesPageClient {...props} />);
  await waitFor(() => expect(screen.getByText(/HTTP 403/)).toBeInTheDocument());
  const button = screen.getByRole("button", { name: "Выгрузить в Excel" });
  expect(button).toBeDisabled();
  fireEvent.click(button);
  expect(exportStaffExcel).not.toHaveBeenCalled();
});

it.each([
  "",
  "q=Иванов&org_group_id=2&org_unit_id=3&department_id=5&position_id=4&status=active&offset=50",
  "q=123&org_group_id=2&department_id=5&position_id=4&status=all&offset=100",
  "q=Иванов&org_group_id=2&org_unit_id=3&department_id=5&position_id=4&status=inactive",
])("exports the same effective filters as the table: %s", async (query) => {
  params = new URLSearchParams(query);
  render(<EmployeesPageClient {...props} />);
  const button = screen.getByRole("button", { name: "Выгрузить в Excel" });
  await waitFor(() => expect(button).toBeEnabled());
  const { limit, offset, ...filters } = getEmployees.mock.calls.at(-1)![0];
  fireEvent.click(button);
  await waitFor(() => expect(exportStaffExcel).toHaveBeenCalledWith(filters));
  expect(exportStaffExcel.mock.calls[0][0]).not.toHaveProperty("offset");
  expect(exportStaffExcel.mock.calls[0][0]).not.toHaveProperty("limit");
  expect(params.toString()).toBe(new URLSearchParams(query).toString());
  if (filters.status === "active") {
    expect(filters).toMatchObject({ q: "Иванов", org_group_id: 2, org_unit_id: "3", department_id: "5", position_id: "4", include_children: true });
  }
});

it("explains an empty result without downloading a file", async () => {
  getEmployees.mockResolvedValue({ items: [], total: 0 });
  render(<EmployeesPageClient {...props} />);
  const button = screen.getByRole("button", { name: "Выгрузить в Excel" });
  await waitFor(() => expect(button).toBeEnabled());
  fireEvent.click(button);
  expect(await screen.findByRole("status")).toHaveTextContent("Нет записей для выгрузки по текущим фильтрам.");
  expect(exportStaffExcel).not.toHaveBeenCalled();
});

it("prevents duplicate downloads and shows export errors", async () => {
  let reject!: (error: Error) => void;
  exportStaffExcel.mockImplementation(() => new Promise((_, rejectPromise) => { reject = rejectPromise; }));
  render(<EmployeesPageClient {...props} />);
  const button = screen.getByRole("button", { name: "Выгрузить в Excel" });
  await waitFor(() => expect(button).toBeEnabled());
  fireEvent.click(button);
  expect(screen.getByRole("button", { name: "Выгрузка…" })).toBeDisabled();
  reject(new Error("Не удалось выгрузить список в Excel."));
  expect(await screen.findByRole("status")).toHaveTextContent("Не удалось выгрузить");
  expect(await screen.findByRole("button", { name: "Выгрузить в Excel" })).toBeEnabled();
});
