// FILE: corpsite-ui/app/admin/system/_lib/visibilityTabLogic.test.ts
import { describe, expect, it } from "vitest";

import type { AdminUser } from "./adminSystemApi.client";
import {
  buildDepartmentUserOptions,
  canSubmitVisibilityAssignment,
  countEmployeesWithoutUserAccount,
  departmentPrefilterRequired,
  extractPositionIdsFromEmployees,
  filterPositionsByDepartmentContext,
  filterUserOptionsByQuery,
  flattenOrgUnitTree,
  targetSelectionRequired,
  toAccessTargetFromDepartment,
} from "./visibilityTabLogic";

describe("visibilityTabLogic", () => {
  const dept = {
    unitId: 10,
    name: "Терапия",
    groupId: 2,
    groupName: "Клинические",
    depth: 0,
  };

  it("flattenOrgUnitTree preserves hierarchy depth and group names", () => {
    const flat = flattenOrgUnitTree(
      [
        {
          unit_id: 10,
          name: "Root",
          group_id: 2,
          children: [{ unit_id: 11, name: "Child" }],
        },
      ],
      0,
      new Map([[2, "Клинические"]]),
    );
    expect(flat).toHaveLength(2);
    expect(flat[0]?.groupName).toBe("Клинические");
    expect(flat[1]?.depth).toBe(1);
  });

  it("buildDepartmentUserOptions filters users by department and enriches labels", () => {
    const users = buildDepartmentUserOptions(
      [
        {
          id: "e1",
          fio: "Иванов И.И.",
          position: { id: 5, name: "Медсестра" },
          department: { name: "Терапия" },
          user: { user_id: 42, login: "ivanov" },
        },
        {
          id: "e2",
          fio: "Без аккаунта",
          user: undefined,
        },
      ],
      [{ user_id: 99, full_name: "Петров", login: "petrov", unit_id: 10 } as AdminUser],
      dept,
    );

    expect(users).toHaveLength(2);
    expect(users.map((u) => u.userId).sort()).toEqual([42, 99]);
    expect(users[0]?.fullName).toContain("Иванов");
    expect(users[0]?.login).toBe("ivanov");
    expect(users[0]?.positionName).toBe("Медсестра");
  });

  it("filterUserOptionsByQuery filters by department-scoped list", () => {
    const all = buildDepartmentUserOptions(
      [
        {
          fio: "Иванов И.И.",
          user: { user_id: 1, login: "ivanov" },
          position: { name: "Медсестра" },
        },
        {
          fio: "Сидоров С.С.",
          user: { user_id: 2, login: "sidorov" },
          position: { name: "Врач" },
        },
      ],
      [],
      dept,
    );
    const filtered = filterUserOptionsByQuery(all, "sidorov");
    expect(filtered).toHaveLength(1);
    expect(filtered[0]?.userId).toBe(2);
  });

  it("DEPARTMENT mode does not require user selection", () => {
    expect(departmentPrefilterRequired("USER")).toBe(true);
    expect(departmentPrefilterRequired("DEPARTMENT")).toBe(false);
    expect(targetSelectionRequired("DEPARTMENT")).toBe(false);
    expect(
      canSubmitVisibilityAssignment({
        mode: "DEPARTMENT",
        selectedDepartment: null,
        selectedUser: null,
        selectedDepartmentTarget: dept,
        selectedPosition: null,
      }),
    ).toBe(true);
    expect(
      canSubmitVisibilityAssignment({
        mode: "USER",
        selectedDepartment: dept,
        selectedUser: null,
        selectedDepartmentTarget: null,
        selectedPosition: null,
      }),
    ).toBe(false);
  });

  it("toAccessTargetFromDepartment maps org unit target for backend DEPARTMENT", () => {
    const target = toAccessTargetFromDepartment(dept);
    expect(target.target_type).toBe("ORG_UNIT");
    expect(target.target_id).toBe(10);
    expect(target.label).toBe("Терапия");
  });

  it("filterPositionsByDepartmentContext limits positions when department selected", () => {
    const staffed = extractPositionIdsFromEmployees([
      { position: { id: 7, name: "Заведующий" } },
    ]);
    const items = [
      { target_type: "POSITION", target_id: 7, label: "Заведующий" },
      { target_type: "POSITION", target_id: 8, label: "Другая" },
    ];
    const filtered = filterPositionsByDepartmentContext(items, staffed, true);
    expect(filtered.map((i) => i.target_id)).toEqual([7]);
  });

  it("countEmployeesWithoutUserAccount reports personnel without login", () => {
    expect(
      countEmployeesWithoutUserAccount([
        { user: { user_id: 1 } },
        { user: undefined },
      ]),
    ).toBe(1);
  });
});
