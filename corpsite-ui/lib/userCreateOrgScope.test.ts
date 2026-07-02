import { describe, expect, it } from "vitest";

import type { TreeNode } from "@/app/directory/org-units/_lib/api.client";
import {
  employeeOrgUnitId,
  findOrgGroupIdForUnit,
} from "./userCreateOrgScope";

describe("userCreateOrgScope", () => {
  const tree: TreeNode[] = [
    {
      id: "10",
      unit_id: 10,
      name: "Group A root",
      group_id: 1,
      children: [
        {
          id: "44",
          unit_id: 44,
          name: "Ambulatory",
          group_id: 1,
          children: [],
        },
      ],
    },
    {
      id: "20",
      unit_id: 20,
      name: "Group B root",
      group_id: 2,
      children: [],
    },
  ];

  it("findOrgGroupIdForUnit resolves group from nested unit", () => {
    expect(findOrgGroupIdForUnit(tree, 44)).toBe(1);
    expect(findOrgGroupIdForUnit(tree, 20)).toBe(2);
    expect(findOrgGroupIdForUnit(tree, 999)).toBeNull();
  });

  it("employeeOrgUnitId reads operational unit from employee details", () => {
    expect(
      employeeOrgUnitId({
        org_unit: { unit_id: 44, name: "Ambulatory" },
      }),
    ).toBe(44);
    expect(employeeOrgUnitId({ org_unit_id: 55 })).toBe(55);
    expect(employeeOrgUnitId(null)).toBeNull();
  });
});
