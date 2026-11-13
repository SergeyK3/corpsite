import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { getPersonnelTypeHeadcountReport } from "../_lib/personnelReportsApi.client";
import PersonnelTypeHeadcountReport from "./PersonnelTypeHeadcountReport";

vi.mock("../_lib/personnelReportsApi.client", () => ({
  getPersonnelTypeHeadcountReport: vi.fn(),
}));

afterEach(() => { cleanup(); vi.clearAllMocks(); });

it("shows five employee groups and their sum without order dates or actions", async () => {
  vi.mocked(getPersonnelTypeHeadcountReport).mockResolvedValue({
    report_code: "personnel_type_headcount",
    groups: [
      { code: 1, name: "Врачи", count: 199 },
      { code: 2, name: "Медсёстры и фельдшеры", count: 199 },
      { code: 3, name: "Санитарки", count: 116 },
      { code: 4, name: "Прочий персонал", count: 57 },
      { code: null, name: "Тип не указан", count: 30 },
    ],
    unknown_employees: Array.from({ length: 30 }, (_, index) => ({
      employee_id: index + 1,
      full_name: `Сотрудник ${index + 1}`,
      org_unit_name: "Терапия",
      position_name: "Специалист",
    })),
    total: 601,
  });
  render(<PersonnelTypeHeadcountReport />);
  const table = await screen.findByTestId("personnel-type-headcount-table");
  expect(within(table).getAllByRole("columnheader").map((cell) => cell.textContent)).toEqual([
    "Тип персонала", "Количество работников",
  ]);
  expect(within(table).getAllByRole("rowheader").map((cell) => cell.textContent)).toEqual([
    "Врачи", "Медсёстры и фельдшеры", "Санитарки", "Прочий персонал", "Тип не указан", "Всего",
  ]);
  expect(screen.getByTestId("personnel-type-headcount-total")).toHaveTextContent("601");
  const unknownButton = screen.getByRole("button", { name: "Показать сотрудников без типа" });
  expect(unknownButton).toHaveTextContent("30");
  expect(screen.queryByTestId("personnel-type-headcount-unknown-details")).not.toBeInTheDocument();
  fireEvent.click(unknownButton);
  const details = screen.getByTestId("personnel-type-headcount-unknown-details");
  expect(within(details).getAllByRole("columnheader").map((cell) => cell.textContent)).toEqual([
    "ФИО", "Отделение", "Должность", "Тип",
  ]);
  expect(within(details).getAllByTestId("personnel-type-headcount-unknown-employee")).toHaveLength(30);
  expect(within(details).getAllByRole("cell").slice(0, 4).map((cell) => cell.textContent)).toEqual([
    "Сотрудник 1", "Терапия", "Специалист", "Не указан",
  ]);
  fireEvent.click(unknownButton);
  expect(screen.queryByTestId("personnel-type-headcount-unknown-details")).not.toBeInTheDocument();
  expect(screen.queryByText("Приказы с непривязанными пунктами")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Дата с")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Дата по")).not.toBeInTheDocument();
  expect(screen.queryByText("Кадровых действий")).not.toBeInTheDocument();
});

it("does not offer expansion when no employees have an unspecified type", async () => {
  vi.mocked(getPersonnelTypeHeadcountReport).mockResolvedValue({
    report_code: "personnel_type_headcount",
    groups: [{ code: null, name: "Тип не указан", count: 0 }],
    unknown_employees: [],
    total: 0,
  });
  render(<PersonnelTypeHeadcountReport />);
  await screen.findByTestId("personnel-type-headcount-table");
  expect(screen.queryByRole("button", { name: "Показать сотрудников без типа" })).not.toBeInTheDocument();
  expect(screen.getByTestId("personnel-type-headcount-unknown")).toHaveTextContent("0");
});
