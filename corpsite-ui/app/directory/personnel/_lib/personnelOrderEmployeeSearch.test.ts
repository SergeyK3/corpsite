import { describe, expect, it } from "vitest";

import {
  mapEmployeesResponseToSearchOptions,
  requireEmployeeIdForItemType,
} from "./personnelOrderEmployeeSearch";

describe("mapEmployeesResponseToSearchOptions", () => {
  it("builds options from { items, total } payload with id/fio", () => {
    const options = mapEmployeesResponseToSearchOptions({
      items: [
        {
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
          rate: null,
          status: "active",
          date_from: null,
          date_to: null,
        },
      ],
      total: 1,
    });

    expect(options).toEqual([
      {
        employee_id: 138,
        full_name: "Макибаева Акмарал Сабитовна",
      },
    ]);
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
  it("requires employee for HIRE", () => {
    expect(requireEmployeeIdForItemType("HIRE", "")).toMatch(/сотрудника/i);
    expect(requireEmployeeIdForItemType("HIRE", "138")).toBeNull();
  });

  it("does not require employee for non-HIRE in this helper", () => {
    expect(requireEmployeeIdForItemType("TRANSFER", "")).toBeNull();
  });
});
