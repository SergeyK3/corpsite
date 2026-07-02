import { describe, expect, it } from "vitest";

import type { EmployeeDetails } from "@/app/directory/employees/_lib/types";
import {
  employeeOrgUnitLabel,
  employeePositionLabel,
  isOperationallyEnrolled,
} from "./employeeOperationalAssignment";

describe("employeeOperationalAssignment", () => {
  const enrolled: EmployeeDetails = {
    id: "42",
    fio: "Test",
    department: null,
    position: { id: 5, name: "Врач" },
    org_unit: { unit_id: 10, name: "ОВЭиПД", code: null, parent_unit_id: null, is_active: true },
    rate: 1,
    status: "active",
    date_from: null,
    date_to: null,
  };

  it("detects operational enrollment when org unit and position exist", () => {
    expect(isOperationallyEnrolled(enrolled)).toBe(true);
    expect(employeeOrgUnitLabel(enrolled)).toBe("ОВЭиПД");
    expect(employeePositionLabel(enrolled)).toBe("Врач");
  });

  it("treats missing position as not enrolled", () => {
    expect(
      isOperationallyEnrolled({
        ...enrolled,
        position: { id: null, name: null },
      }),
    ).toBe(false);
  });
});
