// FILE: corpsite-ui/app/admin/system/_lib/visibilityTabLogic.test.ts
import { describe, expect, it } from "vitest";

import type { AdminUser } from "./adminSystemApi.client";
import {
  buildBulkDepartmentVisibilityPayloads,
  buildDepartmentUserOptions,
  buildVisibilityAssignmentDuplicateMap,
  buildVisibilityTargetReferenceMaps,
  canSubmitVisibilityAssignment,
  clearDepartmentTargetSelection,
  countEmployeesWithoutUserAccount,
  departmentPrefilterRequired,
  extractPositionIdsFromEmployees,
  filterOrgUnitsByGroup,
  filterOrgUnitsByGroupAndQuery,
  filterPositionsByDepartmentContext,
  filterUserOptionsByQuery,
  flattenOrgUnitTree,
  isDuplicateVisibilityAssignment,
  resolveVisibilityTargetDisplay,
  selectAllVisibleDepartmentTargets,
  sortVisibilityAssignmentsForDisplay,
  summarizeVisibilityAssignments,
  targetSelectionRequired,
  toggleDepartmentTargetSelection,
  toAccessTargetFromDepartment,
  visibilityAssignmentDedupeKey,
} from "./visibilityTabLogic";

describe("visibilityTabLogic", () => {
  const clinicalGroupId = 1;
  const adminGroupId = 3;

  const departments = [
    {
      unitId: 10,
      name: "Гинекология",
      groupId: clinicalGroupId,
      groupName: "Клинические",
      depth: 0,
    },
    {
      unitId: 11,
      name: "Инсультный",
      groupId: clinicalGroupId,
      groupName: "Клинические",
      depth: 0,
    },
    {
      unitId: 20,
      name: "Бухгалтерия",
      groupId: adminGroupId,
      groupName: "Административно-хозяйственные",
      depth: 0,
    },
    {
      unitId: 21,
      name: "Отдел кадров",
      groupId: adminGroupId,
      groupName: "Административно-хозяйственные",
      depth: 0,
    },
  ];

  const dept = departments[0]!;

  const targetRefs = buildVisibilityTargetReferenceMaps({
    adminUsers: [
      {
        user_id: 4,
        full_name: "Иванов Иван Иванович",
        login: "ivanov",
      } as AdminUser,
    ],
    orgUnits: departments,
    positions: [{ position_id: 12, name: "Главная медицинская сестра" }],
  });

  it("resolveVisibilityTargetDisplay resolves USER with FIO and login", () => {
    const display = resolveVisibilityTargetDisplay(
      { target_type: "USER", target_user_id: 4 },
      targetRefs,
    );
    expect(display.resolved).toBe(true);
    expect(display.primary).toBe("Иванов Иван Иванович");
    expect(display.secondary).toBe("(ivanov)");
  });

  it("resolveVisibilityTargetDisplay resolves DEPARTMENT with optional group line", () => {
    const display = resolveVisibilityTargetDisplay(
      { target_type: "DEPARTMENT", target_department_id: 20 },
      targetRefs,
    );
    expect(display.resolved).toBe(true);
    expect(display.primary).toBe("Бухгалтерия");
    expect(display.secondary).toBe("Административно-хозяйственные");
  });

  it("resolveVisibilityTargetDisplay resolves POSITION name", () => {
    const display = resolveVisibilityTargetDisplay(
      { target_type: "POSITION", target_position_id: 12 },
      targetRefs,
    );
    expect(display.resolved).toBe(true);
    expect(display.primary).toBe("Главная медицинская сестра");
    expect(display.secondary).toBeNull();
  });

  it("resolveVisibilityTargetDisplay falls back to raw identifier when reference is missing", () => {
    expect(
      resolveVisibilityTargetDisplay(
        { target_type: "USER", target_user_id: 999 },
        targetRefs,
      ),
    ).toMatchObject({
      primary: "USER #999",
      resolved: false,
    });
    expect(
      resolveVisibilityTargetDisplay(
        { target_type: "DEPARTMENT", target_department_id: 73 },
        targetRefs,
      ),
    ).toMatchObject({
      primary: "DEPARTMENT #73",
      resolved: false,
    });
    expect(
      resolveVisibilityTargetDisplay(
        { target_type: "POSITION", target_position_id: 99 },
        targetRefs,
      ),
    ).toMatchObject({
      primary: "POSITION #99",
      resolved: false,
    });
  });

  it("resolveVisibilityTargetDisplay handles deleted or legacy references gracefully", () => {
    const emptyRefs = buildVisibilityTargetReferenceMaps({
      adminUsers: [],
      orgUnits: [],
      positions: [],
    });
    const display = resolveVisibilityTargetDisplay(
      { target_type: "DEPARTMENT", target_department_id: 74 },
      emptyRefs,
    );
    expect(display.primary).toBe("DEPARTMENT #74");
    expect(display.secondary).toBeNull();
    expect(display.resolved).toBe(false);
  });

  it("visibilityAssignmentDedupeKey matches target, scope and can_view_tasks", () => {
    const row = {
      target_type: "DEPARTMENT",
      target_department_id: 73,
      scope_type: "ORGANIZATION",
      can_view_tasks: false,
    };
    expect(visibilityAssignmentDedupeKey(row)).toBe("DEPARTMENT|73|ORGANIZATION|-|0");
    expect(visibilityAssignmentDedupeKey({ ...row, can_view_tasks: true })).not.toBe(
      visibilityAssignmentDedupeKey(row),
    );
  });

  it("isDuplicateVisibilityAssignment marks rows with identical dedupe keys", () => {
    const items = [
      {
        assignment_id: 1,
        target_type: "DEPARTMENT",
        target_department_id: 73,
        scope_type: "ORGANIZATION",
        can_view_tasks: false,
        is_active: true,
      },
      {
        assignment_id: 2,
        target_type: "DEPARTMENT",
        target_department_id: 73,
        scope_type: "ORGANIZATION",
        can_view_tasks: false,
        is_active: true,
      },
      {
        assignment_id: 3,
        target_type: "USER",
        target_user_id: 4,
        scope_type: "ORGANIZATION",
        can_view_tasks: false,
        is_active: true,
      },
    ];
    const duplicateCounts = buildVisibilityAssignmentDuplicateMap(items);
    expect(isDuplicateVisibilityAssignment(items[0]!, duplicateCounts)).toBe(true);
    expect(isDuplicateVisibilityAssignment(items[2]!, duplicateCounts)).toBe(false);
  });

  it("summarizeVisibilityAssignments counts active, revoked and target types", () => {
    const summary = summarizeVisibilityAssignments([
      {
        target_type: "USER",
        target_user_id: 1,
        scope_type: "ORGANIZATION",
        is_active: true,
      },
      {
        target_type: "POSITION",
        target_position_id: 2,
        scope_type: "ORGANIZATION",
        is_active: false,
      },
      {
        target_type: "DEPARTMENT",
        target_department_id: 3,
        scope_type: "ORGANIZATION",
        is_active: true,
      },
    ]);
    expect(summary).toEqual({
      activeCount: 2,
      revokedCount: 1,
      userCount: 1,
      positionCount: 1,
      departmentCount: 1,
      duplicateGroupCount: 0,
    });
  });

  it("sortVisibilityAssignmentsForDisplay groups duplicate keys together", () => {
    const sorted = sortVisibilityAssignmentsForDisplay([
      {
        assignment_id: 10,
        target_type: "USER",
        target_user_id: 1,
        scope_type: "ORGANIZATION",
      },
      {
        assignment_id: 5,
        target_type: "DEPARTMENT",
        target_department_id: 73,
        scope_type: "ORGANIZATION",
      },
      {
        assignment_id: 7,
        target_type: "DEPARTMENT",
        target_department_id: 73,
        scope_type: "ORGANIZATION",
      },
    ]);
    expect(sorted.map((row) => row.assignment_id)).toEqual([7, 5, 10]);
  });

  it("filterOrgUnitsByGroup limits department list to selected group", () => {
    const filtered = filterOrgUnitsByGroup(departments, clinicalGroupId);
    expect(filtered.map((d) => d.unitId)).toEqual([10, 11]);
  });

  it('filterOrgUnitsByGroup with "all groups" returns every department', () => {
    expect(filterOrgUnitsByGroup(departments, null)).toHaveLength(4);
    expect(filterOrgUnitsByGroup(departments, undefined)).toHaveLength(4);
  });

  it("filterOrgUnitsByGroupAndQuery combines group filter and text search", () => {
    const filtered = filterOrgUnitsByGroupAndQuery(departments, adminGroupId, "бух");
    expect(filtered).toHaveLength(1);
    expect(filtered[0]?.name).toBe("Бухгалтерия");
  });

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

  it("filterUserOptionsByQuery filters by department-scoped list in USER mode", () => {
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
        selectedDepartmentTargetIds: new Set([dept.unitId]),
        selectedPosition: null,
      }),
    ).toBe(true);
    expect(
      canSubmitVisibilityAssignment({
        mode: "DEPARTMENT",
        selectedDepartment: null,
        selectedUser: null,
        selectedDepartmentTargetIds: new Set(),
        selectedPosition: null,
      }),
    ).toBe(false);
    expect(
      canSubmitVisibilityAssignment({
        mode: "USER",
        selectedDepartment: dept,
        selectedUser: null,
        selectedDepartmentTargetIds: new Set(),
        selectedPosition: null,
      }),
    ).toBe(false);
  });

  it("selectAllVisibleDepartmentTargets selects every filtered department", () => {
    const adminDepartments = filterOrgUnitsByGroup(departments, adminGroupId);
    const selected = selectAllVisibleDepartmentTargets(new Set(), adminDepartments);
    expect(Array.from(selected).sort()).toEqual([20, 21]);
  });

  it("clearDepartmentTargetSelection removes all selected ids", () => {
    expect(clearDepartmentTargetSelection().size).toBe(0);
    expect(
      clearDepartmentTargetSelection().has(20),
    ).toBe(false);
  });

  it("selection survives search changes for already selected ids", () => {
    let selected = selectAllVisibleDepartmentTargets(new Set(), departments);
    expect(selected.has(20)).toBe(true);
    expect(selected.has(21)).toBe(true);

    const narrowed = filterOrgUnitsByGroupAndQuery(departments, adminGroupId, "бух");
    expect(narrowed).toHaveLength(1);
    expect(selected.has(20)).toBe(true);
    expect(selected.has(21)).toBe(true);

    selected = toggleDepartmentTargetSelection(selected, narrowed[0]!.unitId);
    expect(selected.has(20)).toBe(false);
    expect(selected.has(21)).toBe(true);
  });

  it("buildBulkDepartmentVisibilityPayloads maps selected department ids", () => {
    const payloads = buildBulkDepartmentVisibilityPayloads({
      departmentIds: new Set([21, 20]),
      scopeType: "ORGANIZATION",
      scopeDepartmentId: null,
      scopeDepartmentGroupId: null,
      canViewTasks: true,
    });

    expect(payloads.map((item) => item.departmentId)).toEqual([20, 21]);
    expect(payloads[0]?.payload).toEqual({
      target_type: "DEPARTMENT",
      target_user_id: null,
      target_position_id: null,
      target_department_id: 20,
      scope_type: "ORGANIZATION",
      scope_department_id: null,
      scope_department_group_id: null,
      can_view_personnel: true,
      can_view_tasks: true,
    });
  });

  it("toAccessTargetFromDepartment maps org unit target for backend DEPARTMENT", () => {
    const target = toAccessTargetFromDepartment(dept);
    expect(target.target_type).toBe("ORG_UNIT");
    expect(target.target_id).toBe(10);
    expect(target.label).toBe("Гинекология");
  });

  it("filterPositionsByDepartmentContext limits positions when department selected in POSITION mode", () => {
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

  it("POSITION mode respects department-group filtering when department filter is used", () => {
    const clinicalDepartments = filterOrgUnitsByGroup(departments, clinicalGroupId);
    const staffed = extractPositionIdsFromEmployees([
      { position: { id: 7, name: "Заведующий" } },
    ]);
    const items = [
      { target_type: "POSITION", target_id: 7, label: "Заведующий" },
      { target_type: "POSITION", target_id: 8, label: "Другая" },
    ];
    expect(clinicalDepartments.some((d) => d.unitId === dept.unitId)).toBe(true);
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
