import * as React from "react";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import PersonnelQualificationCategoriesReport, { type QualificationCategoriesReportData } from "./PersonnelQualificationCategoriesReport";

const category = (status: string, status_label: string, valid_until: string | null) => ({
  specialty: "Терапия", category: "first", category_label: "Первая", valid_until,
  status, status_label, document_status: "Наличие файла не установлено",
});
const employee = (id: number, name: string, unitId: number, unitName: string, status: string, label: string, expiry: string | null) => ({
  employee_id: id, person_id: id + 100, full_name: name, org_unit_id: unitId,
  org_unit_name: unitName, categories: [category(status, label, expiry)], pending_categories: [],
});

function renderList(report: QualificationCategoriesReportData) {
  function Harness() {
    const [unitId, setUnitId] = React.useState("");
    return <PersonnelQualificationCategoriesReport report={report} error={null} unitId={unitId} onUnitIdChange={setUnitId} />;
  }
  render(<Harness />);
}

afterEach(cleanup);

describe("PersonnelQualificationCategoriesReport", () => {
  it("shows category names, explicit expiry, statuses and missing-document evidence", async () => {
    renderList({ as_of_date: "2026-11-12", employees: [
      employee(1, "Иванова Анна", 2, "Терапия", "ACTIVE", "Действует", "2027-01-01"),
      { ...employee(2, "Сидорова Мария", 3, "Хирургия", "EXPIRED", "Истекла", "2026-11-11"), pending_categories: ["Высшая"] },
      { employee_id: 3, person_id: 103, full_name: "Петрова Ольга", org_unit_id: 2, org_unit_name: "Терапия", categories: [category("NO_CATEGORY", "Категория не внесена", null)], pending_categories: [] },
    ] });
    expect(screen.getByRole("heading", { name: "Квалификационные категории" })).toBeInTheDocument();
    const expired = await screen.findByTestId("qualification-category-employee-2");
    expect(within(expired).getByText("Первая · Терапия")).toBeInTheDocument();
    expect(within(expired).getByText("2026-11-11")).toBeInTheDocument();
    expect(within(expired).getByText("Истекла")).toHaveClass("bg-red-100");
    expect(within(expired).getByText("Высшая")).toBeInTheDocument();
    expect(within(expired).getByText("На оформлении")).toHaveClass("bg-blue-100");
    expect(within(expired).getByText("Наличие файла не установлено")).toBeInTheDocument();
    expect(screen.getByTestId("qualification-category-employee-3")).toBeInTheDocument();
    expect(within(expired).getByRole("link", { name: "Сидорова Мария" })).toHaveAttribute("href", "/directory/personnel/persons/102/card?section=category");
  });

  it("combines current department, FIO and category status filters", async () => {
    renderList({ as_of_date: "2026-11-12", employees: [
      employee(1, "Иванова Анна", 2, "Терапия", "EXPIRED", "Истекла", "2026-11-11"),
      employee(2, "Иванова Мария", 3, "Хирургия", "EXPIRED", "Истекла", "2026-11-11"),
      employee(3, "Иванова Ольга", 2, "Терапия", "ACTIVE", "Действует", "2027-01-01"),
      employee(4, "Петров Антон", 2, "Терапия", "EXPIRED", "Истекла", "2026-11-11"),
    ] });
    await screen.findByTestId("qualification-category-employee-4");
    fireEvent.change(screen.getByRole("textbox", { name: "Поиск по ФИО" }), { target: { value: "Иванова" } });
    fireEvent.change(screen.getByRole("combobox", { name: "Подразделение" }), { target: { value: "2" } });
    fireEvent.change(screen.getByRole("combobox", { name: "Статус категории" }), { target: { value: "EXPIRED" } });
    expect(screen.getByTestId("qualification-category-employee-1")).toBeInTheDocument();
    expect(screen.queryByTestId("qualification-category-employee-2")).not.toBeInTheDocument();
    expect(screen.queryByTestId("qualification-category-employee-3")).not.toBeInTheDocument();
    expect(screen.queryByTestId("qualification-category-employee-4")).not.toBeInTheDocument();
  });
});
