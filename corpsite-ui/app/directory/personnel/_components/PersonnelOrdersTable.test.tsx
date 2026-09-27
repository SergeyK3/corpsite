import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PersonnelOrdersTable } from "./PersonnelOrdersTable";
import type { PersonnelOrderListItem } from "../_lib/personnelOrdersApi.client";

afterEach(cleanup);

const sampleRow: PersonnelOrderListItem = {
  order_id: 101,
  order_number: "WPPO-101",
  order_date: "2026-07-07",
  order_type_code: "HIRE",
  source_title: "Қызметке қабылдау туралы",
  order_class: "PERSONNEL",
  status: "REGISTERED",
  source_mode: "PAPER",
  created_by: 1,
  item_count: 2,
  employee_ids: [55],
  employee_names: ["Петрова Анна", "Исходное имя без employee_id"],
};

describe("PersonnelOrdersTable", () => {
  it("renders the list API source title verbatim and falls back only for null", () => {
    const { rerender } = render(<PersonnelOrdersTable items={[sampleRow]} />);
    expect(screen.getByText("Қызметке қабылдау туралы")).toBeInTheDocument();
    rerender(
      <PersonnelOrdersTable
        items={[{
          ...sampleRow,
          source_title: "Бала күтіміне байланысты демалыстан жұмысқа шығу туралы",
        }]}
      />,
    );
    expect(
      screen.getByText("Бала күтіміне байланысты демалыстан жұмысқа шығу туралы"),
    ).toBeInTheDocument();
    rerender(<PersonnelOrdersTable items={[{ ...sampleRow, source_title: null }]} />);
    expect(screen.getByTestId("personnel-order-row-101").children[2]).toHaveTextContent("—");
  });
  it("renders empty state", () => {
    render(<PersonnelOrdersTable items={[]} loading={false} emptyMessage="Нет данных" />);
    expect(screen.getByTestId("personnel-orders-empty")).toHaveTextContent("Нет данных");
  });

  it("renders loading state", () => {
    render(<PersonnelOrdersTable items={[]} loading emptyMessage="Нет данных" />);
    expect(screen.getByTestId("personnel-orders-loading")).toBeInTheDocument();
  });

  it("renders every personnel-item name in the employees column", () => {
    const onRowClick = vi.fn();
    render(
      <PersonnelOrdersTable
        items={[sampleRow]}
        onRowClick={onRowClick}
      />,
    );

    expect(screen.getByTestId("personnel-orders-table")).toBeInTheDocument();
    expect(screen.queryByText("PRINT TABLE V2")).not.toBeInTheDocument();
    expect(screen.getByText("WPPO-101")).toBeInTheDocument();
    expect(screen.getByText("Действия")).toBeInTheDocument();
    expect(screen.getByTestId("personnel-order-row-101").children[5]).toHaveTextContent(
      "Петрова Анна, Исходное имя без employee_id",
    );
    expect(screen.queryByTestId("personnel-order-print-101")).not.toBeInTheDocument();
    expect(screen.getByTestId("personnel-order-open-101")).toHaveTextContent("Открыть");

    screen.getByTestId("personnel-order-row-101").click();
    expect(onRowClick).toHaveBeenCalledWith(sampleRow);
  });

  it("renders archived badge when order is archived", () => {
    render(
      <PersonnelOrdersTable
        items={[{ ...sampleRow, is_archived: true }]}
      />,
    );
    expect(screen.getByTestId("personnel-order-archived-badge")).toHaveTextContent("📦 Архив");
  });
});
