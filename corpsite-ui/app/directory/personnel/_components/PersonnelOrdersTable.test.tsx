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
    const onPrintClick = vi.fn();
    render(
      <PersonnelOrdersTable
        items={[sampleRow]}
        onRowClick={onRowClick}
        onPrintClick={onPrintClick}
      />,
    );

    expect(screen.getByTestId("personnel-orders-table")).toBeInTheDocument();
    expect(screen.queryByText("PRINT TABLE V2")).not.toBeInTheDocument();
    expect(screen.getByText("WPPO-101")).toBeInTheDocument();
    expect(screen.getByText("Действия")).toBeInTheDocument();
    expect(screen.getByText("Петрова Анна")).toBeInTheDocument();
    expect(screen.getByTestId("personnel-order-print-101")).toHaveTextContent("Печать");

    screen.getByTestId("personnel-order-row-101").click();
    expect(onRowClick).toHaveBeenCalledWith(sampleRow);

    screen.getByTestId("personnel-order-print-101").click();
    expect(onPrintClick).toHaveBeenCalledWith(sampleRow);
  });
});
