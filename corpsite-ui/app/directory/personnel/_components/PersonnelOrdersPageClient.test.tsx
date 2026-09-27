import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PersonnelOrdersPageClient from "./PersonnelOrdersPageClient";

const navigation = vi.hoisted(() => ({
  params: "",
  replace: vi.fn(),
}));
const api = vi.hoisted(() => ({
  getEmployees: vi.fn(),
  listPersonnelOrders: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: navigation.replace }),
  useSearchParams: () => new URLSearchParams(navigation.params),
}));

vi.mock("@/components/TaskOrgFiltersBar", () => ({ default: () => null }));
vi.mock("@/app/directory/employees/_lib/api.client", () => ({ getEmployees: api.getEmployees }));
vi.mock("./PersonnelOrderCreateDialog", () => ({ default: () => null }));
vi.mock("./PersonnelOrderDetailDrawer", () => ({ default: () => null }));

vi.mock("../_lib/personnelOrdersApi.client", async () => {
  const actual = await vi.importActual<typeof import("../_lib/personnelOrdersApi.client")>(
    "../_lib/personnelOrdersApi.client",
  );
  return { ...actual, listPersonnelOrders: api.listPersonnelOrders };
});

afterEach(() => {
  cleanup();
  navigation.params = "";
  navigation.replace.mockReset();
  api.getEmployees.mockReset();
  api.listPersonnelOrders.mockReset();
});

describe("PersonnelOrdersPageClient employee filter", () => {
  it("selects an employee by full name and applies employee_id filter", async () => {
    api.listPersonnelOrders.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    api.getEmployees.mockResolvedValue({
      items: [{
        id: "791",
        fio: "Райник Анастасия Николаевна",
        department: null,
        position: { id: 6, name: "Врач" },
        org_unit: { unit_id: 50, name: "Администрация", code: null, parent_unit_id: null, is_active: true },
        rate: 1,
        status: "active",
        date_from: null,
        date_to: null,
      }],
      total: 1,
    });

    render(<PersonnelOrdersPageClient />);

    fireEvent.change(screen.getByRole("searchbox", { name: "Сотрудник" }), {
      target: { value: "Райник" },
    });

    await waitFor(() => {
      expect(api.getEmployees).toHaveBeenCalledWith({ q: "Райник", limit: 20, status: "all" });
    });
    fireEvent.click(await screen.findByRole("button", { name: /Райник Анастасия Николаевна/ }));

    expect(navigation.replace).toHaveBeenCalledWith(
      "/directory/personnel/orders?employee_id=791",
    );
  });
});
