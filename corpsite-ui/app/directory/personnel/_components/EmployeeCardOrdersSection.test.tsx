import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import EmployeeCardOrdersSection from "./EmployeeCardOrdersSection";

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
});
