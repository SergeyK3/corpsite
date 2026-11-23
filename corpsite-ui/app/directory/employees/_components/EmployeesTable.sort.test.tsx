import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import EmployeesTable from "./EmployeesTable";

describe("EmployeesTable staff sorting headers", () => {
  afterEach(() => {
    cleanup();
  });

  const baseProps = {
    items: [
      { employee_id: 1, fio: "Борисов Борис", status: "active", employment_rate: 1 },
      { employee_id: 2, fio: "Антонов Антон", status: "inactive", employment_rate: 0.5 },
    ],
    total: 2,
    limit: 50,
    offset: 0,
    loading: false,
    onOpenEmployee: vi.fn(),
    onChangePage: vi.fn(),
    managementView: true,
    directPersonalCardNav: true,
    sortable: true,
    sortColumn: "fio" as const,
    sortOrder: "asc" as const,
    onSortColumn: vi.fn(),
  };

  it("shows ascending indicator on the active column", () => {
    render(<EmployeesTable {...baseProps} />);

    const fioHeader = screen.getByRole("button", { name: /ФИО, сортировка по возрастанию/i });
    expect(fioHeader).toHaveTextContent("↑");
    expect(screen.getByRole("button", { name: "Должность, сортировать" })).toBeInTheDocument();
  });

  it("requests descending order when clicking the active column again", () => {
    const onSortColumn = vi.fn();
    render(<EmployeesTable {...baseProps} onSortColumn={onSortColumn} />);

    fireEvent.click(screen.getByRole("button", { name: /ФИО, сортировка по возрастанию/i }));
    expect(onSortColumn).toHaveBeenCalledWith("fio");
  });

  it("switches to another column in ascending order", () => {
    const onSortColumn = vi.fn();
    render(
      <EmployeesTable
        {...baseProps}
        sortColumn="fio"
        sortOrder="desc"
        onSortColumn={onSortColumn}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Ставка, сортировать" }));
    expect(onSortColumn).toHaveBeenCalledWith("rate");
  });

  it("shows descending indicator when sortOrder is desc", () => {
    render(
      <EmployeesTable
        {...baseProps}
        sortColumn="status"
        sortOrder="desc"
      />,
    );

    expect(screen.getByRole("button", { name: /Статус, сортировка по убыванию/i })).toHaveTextContent("↓");
  });

  it("renders plain headers when sorting is disabled", () => {
    render(
      <EmployeesTable
        {...baseProps}
        sortable={false}
        onSortColumn={undefined}
      />,
    );

    expect(screen.queryByRole("button", { name: /ФИО/i })).not.toBeInTheDocument();
    expect(screen.getByText("ФИО")).toBeInTheDocument();
  });

  it("renders rows in API order without local re-sorting", () => {
    render(
      <EmployeesTable
        {...baseProps}
        sortable={false}
        items={[
          { employee_id: 2, fio: "Яковлев Заведующий", status: "active", employment_rate: 1 },
          { employee_id: 1, fio: "Абдулов Врач", status: "active", employment_rate: 1 },
        ]}
      />,
    );

    const rows = screen.getAllByRole("row").slice(1);
    expect(rows[0]).toHaveTextContent("Яковлев Заведующий");
    expect(rows[1]).toHaveTextContent("Абдулов Врач");
  });
});
