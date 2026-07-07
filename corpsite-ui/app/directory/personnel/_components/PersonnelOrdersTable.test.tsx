import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PersonnelOrdersTable } from "./PersonnelOrdersTable";
import type { PersonnelOrderListItem } from "../_lib/personnelOrdersApi.client";

const sampleRow: PersonnelOrderListItem = {
  order_id: 101,
  order_number: "WPPO-101",
  order_date: "2026-07-07",
  order_type_code: "HIRE",
  order_class: "PERSONNEL",
  status: "REGISTERED",
  source_mode: "PAPER",
  created_by: 1,
  item_count: 2,
  employee_ids: [55],
  employee_names: ["Петрова Анна"],
};

describe("PersonnelOrdersTable", () => {
  it("renders empty state", () => {
    render(<PersonnelOrdersTable items={[]} loading={false} emptyMessage="Нет данных" />);
    expect(screen.getByTestId("personnel-orders-empty")).toHaveTextContent("Нет данных");
  });

  it("renders loading state", () => {
    render(<PersonnelOrdersTable items={[]} loading emptyMessage="Нет данных" />);
    expect(screen.getByTestId("personnel-orders-loading")).toBeInTheDocument();
  });

  it("renders table rows and handles click", () => {
    const onRowClick = vi.fn();
    render(<PersonnelOrdersTable items={[sampleRow]} onRowClick={onRowClick} />);

    expect(screen.getByTestId("personnel-orders-table")).toBeInTheDocument();
    expect(screen.getByText("WPPO-101")).toBeInTheDocument();
    expect(screen.getByText("Петрова Анна")).toBeInTheDocument();

    screen.getByTestId("personnel-order-row-101").click();
    expect(onRowClick).toHaveBeenCalledWith(sampleRow);
  });
});
