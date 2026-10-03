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
  deletePersonnelOrderAsHrHead: vi.fn(),
}));
const currentUser = vi.hoisted(() => ({ value: null as { role_code?: string } | null }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: navigation.replace }),
  useSearchParams: () => new URLSearchParams(navigation.params),
}));

vi.mock("@/components/TaskOrgFiltersBar", () => ({ default: () => null }));
vi.mock("@/lib/currentUser", () => ({ useCurrentUser: () => currentUser.value }));
vi.mock("@/app/directory/employees/_lib/api.client", () => ({ getEmployees: api.getEmployees }));
vi.mock("./PersonnelOrderCreateDialog", () => ({ default: () => null }));
vi.mock("./PersonnelOrderDetailDrawer", () => ({ default: ({ onClose }: { onClose: () => void }) => <button type="button" onClick={onClose}>Закрыть карточку</button> }));

vi.mock("../_lib/personnelOrdersApi.client", async () => {
  const actual = await vi.importActual<typeof import("../_lib/personnelOrdersApi.client")>(
    "../_lib/personnelOrdersApi.client",
  );
  return { ...actual, listPersonnelOrders: api.listPersonnelOrders, deletePersonnelOrderAsHrHead: api.deletePersonnelOrderAsHrHead };
});

afterEach(() => {
  cleanup();
  navigation.params = "";
  navigation.replace.mockReset();
  api.getEmployees.mockReset();
  api.listPersonnelOrders.mockReset();
  api.deletePersonnelOrderAsHrHead.mockReset();
  currentUser.value = null;
});

describe("PersonnelOrdersPageClient employee filter", () => {
  it("shows the HR_HEAD all-status delete button in the journal and uses one confirmation", async () => {
    currentUser.value = { role_code: "HR_HEAD" };
    api.listPersonnelOrders.mockResolvedValue({ items: [{ order_id: 9, order_number: "SIGNED-9", order_date: "2026-10-03", order_type_code: "HIRE", status: "SIGNED", item_count: 0, employee_ids: [], employee_names: [], storage_json: {} }], total: 1, limit: 200, offset: 0 });
    api.deletePersonnelOrderAsHrHead.mockResolvedValue({ status: "SOFT_DELETED", order_id: 9 });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<PersonnelOrdersPageClient />);
    fireEvent.click(await screen.findByRole("button", { name: "Удалить" }));
    await waitFor(() => expect(api.deletePersonnelOrderAsHrHead).toHaveBeenCalledWith(9));
  });

  it("returns to an explicit quality-control return_to after a refreshed deep link is closed", async () => {
    navigation.params = "order_id=8&tab=data&return_to=%2Fadmin%2Fsystem%3Fsection%3Dquality-control";
    api.listPersonnelOrders.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });

    render(<PersonnelOrdersPageClient />);
    fireEvent.click(await screen.findByRole("button", { name: "Закрыть карточку" }));

    expect(navigation.replace).toHaveBeenCalledWith("/admin/system?section=quality-control");
  });

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
      "/directory/personnel/orders?employee_id=791&record_quality=WORKING",
    );
  });
});
