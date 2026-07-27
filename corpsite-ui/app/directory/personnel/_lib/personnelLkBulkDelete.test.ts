import { describe, expect, it } from "vitest";

import {
  buildEmployeeBulkDeleteConfirmMessage,
  formatEmployeeBulkDeleteFailureLines,
  formatEmployeeBulkDeleteSummary,
  listSelectableEmployeeIds,
} from "./personnelLkBulkDelete";
import type { PersonnelLkRegistryItem } from "./personnelLkApi.client";

const employeeRow = (employeeId: number, fio: string): PersonnelLkRegistryItem => ({
  person_id: employeeId,
  record_kind: "employee",
  id: employeeId,
  employee_id: employeeId,
  active_application_id: null,
  fio,
  iin: null,
  rate: 1,
  status: "active",
  application_status: null,
});

describe("personnelLkBulkDelete", () => {
  it("lists only employee rows with employee_id", () => {
    const ids = listSelectableEmployeeIds([
      employeeRow(100, "Иванов"),
      {
        person_id: 5,
        record_kind: "applicant",
        id: null,
        employee_id: null,
        active_application_id: 10,
        fio: "Петров",
        iin: null,
        rate: 0.5,
        status: "applicant",
        application_status: "registered",
      },
    ]);
    expect(ids).toEqual([100]);
  });

  it("builds confirm message with names and irreversibility warning", () => {
    const message = buildEmployeeBulkDeleteConfirmMessage(["Иванов Иван", "Сидоров"]);
    expect(message).toContain("Иванов Иван");
    expect(message).toContain("Сидоров");
    expect(message).toContain("без возможности восстановления");
  });

  it("formats summary for full and partial success", () => {
    expect(
      formatEmployeeBulkDeleteSummary({
        requested: 2,
        deleted: [{ employee_id: 1 }, { employee_id: 2 }],
        failed: [],
      }),
    ).toBe("Удалено сотрудников: 2.");

    expect(
      formatEmployeeBulkDeleteSummary({
        requested: 2,
        deleted: [{ employee_id: 1 }],
        failed: [{ employee_id: 2, error_code: "NOT_FOUND", message: "Сотрудник не найден." }],
      }),
    ).toBe("Удалено: 1. Не удалено: 1.");
  });

  it("formats failure lines with safe messages", () => {
    const lines = formatEmployeeBulkDeleteFailureLines(
      {
        requested: 1,
        deleted: [],
        failed: [{ employee_id: 42, error_code: "NOT_FOUND", message: "Сотрудник не найден." }],
      },
      new Map([[42, "Иванов Иван"]]),
    );
    expect(lines).toEqual(["Иванов Иван: Сотрудник не найден."]);
  });
});
