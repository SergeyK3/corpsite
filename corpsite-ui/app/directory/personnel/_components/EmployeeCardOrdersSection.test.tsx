import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import EmployeeCardOrdersSection from "./EmployeeCardOrdersSection";
import { listPersonnelOrders, type PersonnelOrderListItem } from "../_lib/personnelOrdersApi.client";

vi.mock("../_lib/personnelOrdersApi.client", async () => {
  const actual = await vi.importActual<typeof import("../_lib/personnelOrdersApi.client")>("../_lib/personnelOrdersApi.client");
  return { ...actual, listPersonnelOrders: vi.fn().mockResolvedValue({ items: [], total: 0 }) };
});

describe("EmployeeCardOrdersSection", () => {
  it("opens manual order creation with the exact current employee id", async () => {
    render(<EmployeeCardOrdersSection employeeId="42" />);

    await waitFor(() => expect(screen.getByText(/Приказов по этому сотруднику/i)).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "Создать приказ" })).toHaveAttribute(
      "href",
      "/directory/personnel/orders?employee_id=42&create=1",
    );
  });

  it("shows the common label instead of the childcare-return technical code", async () => {
    const childcareReturn: PersonnelOrderListItem = {
      order_id: 7,
      order_number: "7-К",
      order_date: "2026-09-26",
      order_type_code: "RETURN_FROM_CHILDCARE_LEAVE",
      order_class: "PERSONNEL",
      status: "DRAFT",
      source_mode: "PAPER",
      created_by: 1,
      item_count: 1,
      employee_ids: [42],
      employee_names: ["Тестовый сотрудник"],
    };
    vi.mocked(listPersonnelOrders).mockResolvedValueOnce({ items: [childcareReturn], total: 1 });

    render(<EmployeeCardOrdersSection employeeId="42" />);

    expect(await screen.findByText(/Выход из отпуска по уходу за ребёнком/)).toBeInTheDocument();
    expect(screen.queryByText("RETURN_FROM_CHILDCARE_LEAVE")).not.toBeInTheDocument();
  });
});
