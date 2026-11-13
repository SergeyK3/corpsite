import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import PositionAssignmentReport from "./PositionAssignmentReport";

const apiFetchJson = vi.fn();
vi.mock("@/lib/api", () => ({ apiFetchJson: (...args: unknown[]) => apiFetchJson(...args) }));

beforeEach(() => {
  apiFetchJson.mockReset();
  apiFetchJson.mockResolvedValue({
    as_of: "2026-11-13",
    independent_assignment_name_available: false,
    position_active_flag_available: false,
    metrics: {
      assignment_names: 1,
      catalog_positions: 2,
      active_catalog_positions: null,
      inactive_catalog_positions: null,
      assignment_names_missing_in_catalog: null,
      catalog_without_active_assignments: 1,
    },
    assignment_names: [{
      name: "Врач", normalized_name: "врач", employee_count: 1,
      employees: [{ employee_id: 7, full_name: "Анна Иванова", departments: ["Терапия"] }],
      positions: [{ position_id: 10, name: "Врач", employee_count: 1,
        employees: [{ employee_id: 7, full_name: "Анна Иванова", departments: ["Терапия"] }] }],
      possible_duplicate_ids: [],
    }],
    catalog_positions: [
      { position_id: 10, name: "Врач", type_code: 1, type_name: "Врачи", is_active: null,
        employee_count: 1, employees: [{ employee_id: 7, full_name: "Анна Иванова", departments: ["Терапия"] }],
        possible_duplicate_ids: [] },
      { position_id: 11, name: "Историческая должность", type_code: null, type_name: null, is_active: null,
        employee_count: 0, employees: [], possible_duplicate_ids: [] },
    ],
    assignment_names_missing_in_catalog: [],
    catalog_without_active_assignments: [
      { position_id: 11, name: "Историческая должность", type_code: null, type_name: null, is_active: null,
        employee_count: 0, employees: [], possible_duplicate_ids: [] },
    ],
    missing_position_references: [],
  });
});

test("all indicators open matching detail rows without claiming independent assignment names", async () => {
  render(<PositionAssignmentReport />);
  await waitFor(() => expect(apiFetchJson).toHaveBeenCalledTimes(1));
  expect(apiFetchJson).toHaveBeenCalledWith("/directory/personnel/reports/position-assignment-reconciliation");

  const occupiedPositions = screen.getByRole("button", { name: /Должности справочника, которые сейчас занимают сотрудники/ });
  expect(within(occupiedPositions).getByText("Одно и то же название должности в разных отделениях считается один раз")).toBeTruthy();
  fireEvent.click(occupiedPositions);
  const names = screen.getByTestId("position-report-assignment-names");
  expect(within(names).getAllByText(/Врач/).length).toBeGreaterThan(0);
  expect(within(names).getByText(/Занимаемые должности · 1/)).toBeTruthy();

  fireEvent.click(screen.getByRole("button", { name: /Позиций в справочнике/ }));
  expect(screen.getAllByText(/ID 10/).length).toBeGreaterThan(0);
  expect(screen.getAllByText(/ID 11/).length).toBeGreaterThan(0);
  expect(screen.getByText(/Позиции справочника · 2/)).toBeTruthy();

  fireEvent.click(screen.getByRole("button", { name: /Названия из назначений, которых нет в справочнике/ }));
  expect(screen.getByText(/Независимое сравнение названий недоступно/)).toBeTruthy();
  expect(screen.getByText(/Ссылок на отсутствующую позицию: 0/)).toBeTruthy();

  fireEvent.click(screen.getByRole("button", { name: /Позиции справочника без действующих назначений/ }));
  expect(screen.getByText(/Позиции без действующих назначений · 1/)).toBeTruthy();
  expect(screen.getByText(/не означает, что позицию можно удалить/)).toBeTruthy();
});
