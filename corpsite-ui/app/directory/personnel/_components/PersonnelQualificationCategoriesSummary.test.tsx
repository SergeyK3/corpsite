import * as React from "react";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";

import PersonnelQualificationCategoriesSummary, { qualificationCategoryDetailedTables, qualificationCategorySummary } from "./PersonnelQualificationCategoriesSummary";
import { qualificationEmployeesInUnit, type QualificationCategoriesReportData } from "./PersonnelQualificationCategoriesReport";

const item = (status: string) => ({ specialty: "", category: status === "NO_CATEGORY" ? "" : "first", category_label: "Первая", valid_until: null, status, status_label: status, document_status: "Наличие файла не установлено" });
const report: QualificationCategoriesReportData = {
  as_of_date: "2026-11-12",
  employees: [
    { employee_id: 1, person_id: 101, full_name: "А", org_unit_id: 2, org_unit_name: "Отделение А", categories: [item("ACTIVE"), item("EXPIRED")], pending_categories: ["Высшая"] },
    { employee_id: 2, person_id: 102, full_name: "Б", org_unit_id: 2, org_unit_name: "Отделение А", categories: [item("EXPIRING_SOON")], pending_categories: [] },
    { employee_id: 3, person_id: 103, full_name: "В", org_unit_id: 3, org_unit_name: "Отделение Б", categories: [item("NO_EXPIRY")], pending_categories: ["Первая"] },
    { employee_id: 4, person_id: 104, full_name: "Г", org_unit_id: 2, org_unit_name: "Отделение А", categories: [item("NO_CATEGORY")], pending_categories: [] },
  ],
};

afterEach(cleanup);

it("counts unique employees from the list selection and keeps pending separate", () => {
  const all = qualificationCategorySummary(qualificationEmployeesInUnit(report, ""));
  expect(all).toMatchObject({ total: 4, pending: 2, statuses: { ACTIVE: 1, EXPIRING_SOON: 1, EXPIRED: 1, NO_EXPIRY: 1, NO_CATEGORY: 1 } });
  const unit = qualificationCategorySummary(qualificationEmployeesInUnit(report, "2"));
  expect(unit).toMatchObject({ total: 3, pending: 1, statuses: { ACTIVE: 1, EXPIRING_SOON: 1, EXPIRED: 1, NO_EXPIRY: 0, NO_CATEGORY: 1 } });
  expect(qualificationEmployeesInUnit(report, "2").filter((employee) => employee.categories.some((category) => category.status === "EXPIRED"))).toHaveLength(unit.statuses.EXPIRED);
});

it("updates all summary numbers with the department filter", () => {
  function Harness() {
    const [unitId, setUnitId] = React.useState("");
    return <PersonnelQualificationCategoriesSummary report={report} error={null} unitId={unitId} onUnitIdChange={setUnitId} />;
  }
  render(<Harness />);
  expect(screen.getByTestId("qualification-summary-total")).toHaveTextContent("4");
  expect(screen.getByTestId("qualification-summary-pending")).toHaveTextContent("2");
  fireEvent.change(screen.getByRole("combobox", { name: "Подразделение" }), { target: { value: "2" } });
  expect(screen.getByTestId("qualification-summary-total")).toHaveTextContent("3");
  expect(screen.getByTestId("qualification-summary-NO_EXPIRY")).toHaveTextContent("0");
  expect(screen.getByTestId("qualification-summary-pending")).toHaveTextContent("1");
});

it("counts explicit dates at 0, 30 and 90 days inclusively without expired or duplicate employees", () => {
  const category = (level: string, date: string | null, status: string) => ({ ...item(status), category: level, valid_until: date });
  const rows: QualificationCategoriesReportData = { as_of_date: "2026-11-12", employees: [
    { employee_id: 1, person_id: 101, full_name: "А", org_unit_id: 2, org_unit_name: "А", categories: [category("highest", "2026-11-12", "EXPIRING_SOON"), category("highest", "2026-12-12", "EXPIRING_SOON")], pending_categories: [] },
    { employee_id: 2, person_id: 102, full_name: "Б", org_unit_id: 2, org_unit_name: "А", categories: [category("first", "2026-12-12", "EXPIRING_SOON")], pending_categories: [] },
    { employee_id: 3, person_id: 103, full_name: "В", org_unit_id: 2, org_unit_name: "А", categories: [category("second", "2026-12-13", "ACTIVE")], pending_categories: [] },
    { employee_id: 4, person_id: 104, full_name: "Г", org_unit_id: 3, org_unit_name: "Б", categories: [category("highest", "2027-02-10", "ACTIVE")], pending_categories: [] },
    { employee_id: 5, person_id: 105, full_name: "Д", org_unit_id: 3, org_unit_name: "Б", categories: [category("first", "2027-02-11", "ACTIVE")], pending_categories: [] },
    { employee_id: 6, person_id: 106, full_name: "Е", org_unit_id: 3, org_unit_name: "Б", categories: [category("second", "2026-11-11", "EXPIRED")], pending_categories: [] },
    { employee_id: 7, person_id: 107, full_name: "Ж", org_unit_id: 2, org_unit_name: "А", categories: [category("highest", null, "NO_EXPIRY")], pending_categories: [] },
    { employee_id: 8, person_id: 108, full_name: "З", org_unit_id: 2, org_unit_name: "А", categories: [{ ...item("NO_CATEGORY"), category: "" }], pending_categories: ["Высшая"] },
    { employee_id: 9, person_id: 109, full_name: "И", org_unit_id: 2, org_unit_name: "А", categories: [category("first", "2026-12-12", "EXPIRING_SOON"), category("first", "2027-02-10", "ACTIVE")], pending_categories: [] },
  ] };
  const all = qualificationCategoryDetailedTables(rows.employees, rows.as_of_date);
  expect(all.levels.map((row) => row.all)).toEqual([3, 3, 2, 1]);
  expect(all.expiry.map((row) => row.all)).toEqual([3, 5, 1]);
  const unit = qualificationCategoryDetailedTables(qualificationEmployeesInUnit(rows, "2"), rows.as_of_date);
  expect(unit.levels.map((row) => row.all)).toEqual([2, 2, 1, 1]);
  expect(unit.levels[3].all).toBe(qualificationCategorySummary(qualificationEmployeesInUnit(rows, "2")).statuses.NO_CATEGORY);
  expect(unit.expiry.map((row) => row.all)).toEqual([3, 4, 1]);
});

it("applies the department filter to both new tables and leaves unclassified roles unknown", () => {
  function Harness() {
    const [unitId, setUnitId] = React.useState("");
    return <PersonnelQualificationCategoriesSummary report={report} error={null} unitId={unitId} onUnitIdChange={setUnitId} />;
  }
  render(<Harness />);
  expect(screen.getByTestId("qualification-level-first-all")).toHaveTextContent("3");
  expect(screen.getByTestId("qualification-level-NO_CATEGORY-all")).toHaveTextContent("1");
  expect(screen.getByTestId("qualification-level-NO_CATEGORY-all")).toHaveTextContent(screen.getByTestId("qualification-summary-NO_CATEGORY").textContent || "");
  expect(screen.getByTestId("qualification-expiry-NO_EXPIRY-all")).toHaveTextContent("1");
  const levelTable = screen.getByTestId("qualification-level-table");
  expect(within(levelTable).getAllByLabelText("Нет классификации текущей должности")).toHaveLength(8);
  fireEvent.change(screen.getByRole("combobox", { name: "Подразделение" }), { target: { value: "2" } });
  expect(screen.getByTestId("qualification-level-first-all")).toHaveTextContent("2");
  expect(screen.getByTestId("qualification-level-NO_CATEGORY-all")).toHaveTextContent(screen.getByTestId("qualification-summary-NO_CATEGORY").textContent || "");
  expect(screen.getByTestId("qualification-expiry-NO_EXPIRY-all")).toHaveTextContent("0");
});
