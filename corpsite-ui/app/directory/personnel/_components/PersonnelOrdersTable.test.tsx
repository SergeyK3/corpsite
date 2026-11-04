import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PersonnelOrdersTable } from "./PersonnelOrdersTable";
import type { PersonnelOrderListItem } from "../_lib/personnelOrdersApi.client";
import { PERSONNEL_ORDER_TYPES } from "../_lib/personnelOrderLabels";
import { PERSONNEL_ORDER_CANONICAL_TITLES } from "../_lib/personnelOrderCanonicalTitles";

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
  it("renders a single KK catalogue title by type regardless of the saved source title", () => {
    const { rerender } = render(<PersonnelOrdersTable items={[sampleRow]} />);
    expect(screen.getByRole("columnheader", {name: "Тип приказа"})).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", {name: "Исходное название"})).not.toBeInTheDocument();
    expect(screen.queryByRole("columnheader", {name: "Тип", exact: true})).not.toBeInTheDocument();
    expect(within(screen.getByTestId("personnel-order-row-101")).getAllByText("Жұмысқа қабылдау туралы")).toHaveLength(1);
    expect(screen.queryByText(sampleRow.source_title!)).not.toBeInTheDocument();
    rerender(
      <PersonnelOrdersTable
        items={[{
          ...sampleRow,
          source_title: "Бала күтіміне байланысты демалыстан жұмысқа шығу туралы",
        }]}
      />,
    );
    expect(screen.getByText("Жұмысқа қабылдау туралы")).toBeInTheDocument();
    expect(screen.queryByText("Бала күтіміне байланысты демалыстан жұмысқа шығу туралы")).not.toBeInTheDocument();
    rerender(<PersonnelOrdersTable items={[{ ...sampleRow, source_title: null }]} />);
    expect(screen.getByTestId("personnel-order-row-101").children[2]).toHaveTextContent("Жұмысқа қабылдау туралы");
  });
  it("uses KK catalogue names for every supported type, including reconstructed composite orders, without changing source data", () => {
    const journalTitle = "  Қоса\u00a0 атқару туралыы\n";
    const rows = PERSONNEL_ORDER_TYPES.map((code, index) => ({...sampleRow, order_id: index + 1,
      order_type_code: code, source_title: "Исходная опичатка", storage_json: {source_title: journalTitle, reconstruction_status: "NEEDS_DOCX_REVIEW"}}));
    const before = JSON.stringify(rows);
    render(<PersonnelOrdersTable items={rows} />);
    for (const row of rows) {
      const title = row.order_type_code === "COMPOSITE" ? "Кадрлық өзгерістер туралы" : PERSONNEL_ORDER_CANONICAL_TITLES[row.order_type_code].kk;
      const rendered = screen.getByTestId(`personnel-order-row-${row.order_id}`);
      expect(rendered.children[2]).toHaveTextContent(title);
      expect(within(rendered).getAllByText(title, {exact: true})).toHaveLength(1);
      expect(rendered.children).toHaveLength(7);
      expect(within(rendered).getByText("Восстановлен, требует сверки")).toBeInTheDocument();
    }
    expect(JSON.stringify(rows)).toBe(before);
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
    expect(screen.getByTestId("personnel-order-row-101").children[4]).toHaveTextContent(
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

  it("renders the HR_HEAD delete action beside open and does not row-open on delete", () => {
    const onRowClick = vi.fn();
    const onDelete = vi.fn();
    render(<PersonnelOrdersTable items={[sampleRow]} onRowClick={onRowClick} onDelete={onDelete} />);
    fireEvent.click(screen.getByTestId("personnel-order-delete-101"));
    expect(onDelete).toHaveBeenCalledWith(sampleRow);
    expect(onRowClick).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Удалить" })).toBeInTheDocument();
  });
});
