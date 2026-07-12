import { describe, expect, it } from "vitest";

import {
  mapEmployeesResponseToSearchOptions,
  requireEmployeeIdForItemType,
} from "./personnelOrderEmployeeSearch";

describe("mapEmployeesResponseToSearchOptions", () => {
  const activeRow = {
    id: "138",
    fio: "Макибаева Акмарал Сабитовна",
    department: null,
    position: { id: 86, name: "Руководитель отдела кадров" },
    org_unit: {
      unit_id: 73,
      name: "Отдел кадров",
      code: null,
      parent_unit_id: null,
      is_active: true,
    },
    rate: "1",
    status: "active",
    date_from: null,
    date_to: null,
  };

  it("builds options from { items, total } payload with placement fields", () => {
    const options = mapEmployeesResponseToSearchOptions({
      items: [activeRow],
      total: 1,
    });

    expect(options).toEqual([
      {
        employee_id: 138,
        full_name: "Макибаева Акмарал Сабитовна",
        org_unit_id: 73,
        org_unit_name: "Отдел кадров",
        position_id: 86,
        position_name: "Руководитель отдела кадров",
        rate: "1",
        status: "active",
      },
    ]);
  });

  it("filters inactive employees when activeOnly is true", () => {
    const options = mapEmployeesResponseToSearchOptions(
      {
        items: [
          activeRow,
          {
            ...activeRow,
            id: "200",
            fio: "Бывший Сотрудник",
            status: "inactive",
          },
        ],
        total: 2,
      },
      { activeOnly: true },
    );

    expect(options).toHaveLength(1);
    expect(options[0]?.employee_id).toBe(138);
  });

  it("keeps rows with unknown status when activeOnly is true", () => {
    const options = mapEmployeesResponseToSearchOptions(
      {
        items: [{ ...activeRow, status: "unknown" }],
        total: 1,
      },
      { activeOnly: true },
    );

    expect(options).toHaveLength(1);
    expect(options[0]?.employee_id).toBe(138);
  });

  it("returns empty list for empty items", () => {
    expect(mapEmployeesResponseToSearchOptions({ items: [], total: 0 })).toEqual([]);
  });

  it("ignores rows without a valid id", () => {
    expect(
      mapEmployeesResponseToSearchOptions({
        items: [
          {
            id: "",
            fio: "Без id",
            department: null,
            position: null,
            org_unit: null,
            rate: null,
            status: "active",
            date_from: null,
            date_to: null,
          },
        ],
        total: 1,
      }),
    ).toEqual([]);
  });
});

describe("requireEmployeeIdForItemType", () => {
  it("requires employee for TRANSFER and TERMINATION", () => {
    expect(requireEmployeeIdForItemType("TRANSFER", "")).toMatch(/сотрудника/i);
    expect(requireEmployeeIdForItemType("TERMINATION", "")).toMatch(/сотрудника/i);
    expect(requireEmployeeIdForItemType("TRANSFER", "138")).toBeNull();
  });

  it("requires employee for RATE_CHANGE", () => {
    expect(requireEmployeeIdForItemType("RATE_CHANGE", "")).toMatch(/сотрудника/i);
    expect(requireEmployeeIdForItemType("RATE_CHANGE", "42")).toBeNull();
  });

  it("does not require employee for legacy HIRE", () => {
    expect(requireEmployeeIdForItemType("HIRE", "")).toBeNull();
    expect(requireEmployeeIdForItemType("HIRE", "", { pendingNewEmployee: true })).toBeNull();
    expect(requireEmployeeIdForItemType("HIRE", "", { pendingNewEmployee: false })).toBeNull();
  });
});
