import { describe, expect, it } from "vitest";

import { mapEmployee, type EmployeeDTO } from "./types";

function employeeDto(overrides: Partial<EmployeeDTO> = {}): EmployeeDTO {
  return {
    id: "224",
    fio: "Абзалқызы Толғанай",
    department: { id: 73, name: "Отдел кадров" },
    position: { id: 340, name: "Менеджер УЧР" },
    org_unit: {
      unit_id: 73,
      name: "Отдел кадров",
      code: null,
      parent_unit_id: null,
      is_active: true,
    },
    rate: null,
    status: "inactive",
    date_from: null,
    date_to: null,
    ...overrides,
  };
}

describe("mapEmployee", () => {
  it("keeps an explicitly inactive employee inactive when the termination date is unknown", () => {
    expect(mapEmployee(employeeDto()).isActive).toBe(false);
  });
});
