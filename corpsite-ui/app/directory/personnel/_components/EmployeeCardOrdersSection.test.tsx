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
      "/directory/personnel/orders?employee_id=42&record_quality=ALL&create=1",
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
    vi.mocked(listPersonnelOrders).mockResolvedValueOnce({ items: [childcareReturn], total: 1, limit: 10, offset: 0 });

    render(<EmployeeCardOrdersSection employeeId="42" />);

    expect(await screen.findByText(/Выход из отпуска по уходу за ребёнком/)).toBeInTheDocument();
    expect(screen.queryByText("RETURN_FROM_CHILDCARE_LEAVE")).not.toBeInTheDocument();
  });

  it.each(["SIGNED", "REGISTERED"])("opens an imported %s order with its official number", async (status) => {
    const imported: PersonnelOrderListItem = {
      order_id: 47, order_number: "DEMO-47", order_date: "2026-11-12",
      order_type_code: "HIRE", order_class: "PERSONNEL", status,
      source_mode: "DIGITAL", created_by: 1, item_count: 1,
      employee_ids: [42], employee_names: ["Synthetic Demo Employee"],
      storage_json: { technical_record: true, record_quality: "TECHNICAL_RECORD", import_source_order_number: "CSV-PILOT-47" },
    };
    vi.mocked(listPersonnelOrders).mockResolvedValueOnce({ items: [imported], total: 1, limit: 10, offset: 0 });
    render(<EmployeeCardOrdersSection employeeId="42" />);
    const link = await screen.findByRole("link", { name: /DEMO-47/ });
    expect(link.getAttribute("href")).toContain("order_id=47");
    expect(link.getAttribute("href")).toContain("record_quality=ALL");
    expect(listPersonnelOrders).toHaveBeenCalledWith({ employee_id: 42, record_quality: "ALL", limit: 10, offset: 0 });
  });
});
