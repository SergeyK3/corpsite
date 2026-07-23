import { describe, expect, it } from "vitest";

import {
  buildBulkDeleteConfirmMessage,
  buildBulkDeleteResultRows,
  canOfferNoParentOption,
  collectDescendantIds,
  DEPENDENCY_DISPLAY_ORDER,
  DEPENDENCY_LABELS,
  dependencyLabel,
  formatBulkDeleteSummary,
  formatDependencyList,
  isSingleRootInvariantDetail,
  mapAdminOrgUnitsApiError,
  normalizeBulkDeleteSelection,
  resolveGroupLabel,
  SINGLE_ROOT_INVARIANT_MESSAGE,
} from "./adminOrgUnitsApi.client";

describe("adminOrgUnitsApi.client helpers", () => {
  it("formats non-zero dependencies with localized labels", () => {
    const lines = formatDependencyList({ employees: 3, child_org_units: 0, users: 1 });
    expect(lines).toHaveLength(2);
    expect(lines[0]).toBe("Пользователи: 1");
    expect(lines[1]).toBe("Сотрудники: 3");
  });

  it("orders dependencies by operational importance", () => {
    const lines = formatDependencyList({
      legacy_position_mapping: 1,
      active_employees: 2,
      users: 1,
      person_assignments: 3,
    });
    expect(lines[0]).toBe("Активные сотрудники: 2");
    expect(lines[1]).toBe("Пользователи: 1");
    expect(lines[2]).toBe("Назначения: 3");
    expect(lines[3]).toBe("Наследуемые сопоставления должностей: 1");
  });

  it("has fully localized labels without snake_case fallbacks", () => {
    expect(DEPENDENCY_LABELS.employees).toBe("Сотрудники");
    expect(DEPENDENCY_LABELS.active_employees).toBe("Активные сотрудники");
    expect(DEPENDENCY_LABELS.person_assignments).toBe("Назначения");
    expect(DEPENDENCY_LABELS.org_unique_position).toBe("Уникальные должности");
    expect(DEPENDENCY_LABELS.legacy_position_mapping).toBe("Наследуемые сопоставления должностей");
    expect(DEPENDENCY_LABELS.department_recoding).toBe("Перекодировка подразделений");
    expect(dependencyLabel("unknown_internal_key")).toBe("Связанные записи");
  });

  it("keeps display order list aligned with product priority", () => {
    expect(DEPENDENCY_DISPLAY_ORDER.slice(0, 7)).toEqual([
      "active_employees",
      "users",
      "employees",
      "regular_tasks",
      "employee_events",
      "person_assignments",
      "org_unique_position",
    ]);
  });

  it("detects single-root invariant detail", () => {
    expect(isSingleRootInvariantDetail("single-root invariant: root already exists")).toBe(true);
    const message = mapAdminOrgUnitsApiError(
      { body: { detail: "single-root invariant: root already exists" } },
      "fallback",
    );
    expect(message).toBe(SINGLE_ROOT_INVARIANT_MESSAGE);
  });

  it("builds structured bulk delete rows from API response", () => {
    const rows = buildBulkDeleteResultRows(
      {
        deleted_ids: [1],
        failed: [
          {
            id: 2,
            name: "Отдел B",
            reason_code: "SUBTREE_HAS_DEPENDENCIES",
            message: "Подразделение используется в системе",
            blocked_units: [{ id: 3, name: "Дочерний", dependencies: { users: 1 } }],
          },
        ],
        requested: 2,
      },
      new Map([
        [1, "Отдел A"],
        [2, "Отдел B"],
      ]),
    );
    expect(rows.deleted).toHaveLength(1);
    expect(rows.deleted[0].name).toBe("Отдел A");
    expect(rows.failed[0].name).toBe("Отдел B");
    expect(rows.failed[0].blocked_units?.[0].name).toBe("Дочерний");
  });

  it("collects descendant ids from flat org unit list", () => {
    const items = [
      { unit_id: 1, parent_unit_id: null, name: "Root", is_active: true },
      { unit_id: 2, parent_unit_id: 1, name: "Child", is_active: true },
      { unit_id: 3, parent_unit_id: 2, name: "Grandchild", is_active: true },
      { unit_id: 4, parent_unit_id: 1, name: "Other", is_active: true },
    ];
    expect(Array.from(collectDescendantIds(items, 1)).sort()).toEqual([2, 3, 4]);
  });

  it("normalizes bulk delete selection to roots when parent and child selected", () => {
    const items = [
      { unit_id: 1, parent_unit_id: null, name: "Root", is_active: true },
      { unit_id: 2, parent_unit_id: 1, name: "Child", is_active: true },
    ];
    const normalized = normalizeBulkDeleteSelection(items, [1, 2]);
    expect(normalized.roots).toEqual([1]);
    expect(normalized.covered).toEqual([{ id: 2, coveredBy: 1 }]);
  });

  it("builds bulk delete confirm message with descendant count", () => {
    const message = buildBulkDeleteConfirmMessage({
      requested: 2,
      roots: [
        {
          id: 1,
          name: "Root",
          descendants: [{ id: 2, name: "Child" }],
          subtree_size: 2,
        },
      ],
      skipped_as_covered: [{ id: 2, covered_by: 1 }],
      not_found: [],
    });
    expect(message).toContain("1 выбранных");
    expect(message).toContain("1 дочерними");
  });

  it("formats bulk delete summary with skip reasons", () => {
    const summary = formatBulkDeleteSummary({
      deleted_ids: [1],
      failed: [
        {
          id: 2,
          name: "Отдел B",
          reason_code: "ORG_UNIT_HAS_DEPENDENCIES",
          message: "Есть зависимости",
        },
      ],
      requested: 2,
    });
    expect(summary).toContain("Удалено 1 из 2");
    expect(summary).toContain("Отдел B (ID 2): Есть зависимости");
  });

  it("resolves group label from catalog fallback", () => {
    const label = resolveGroupLabel(2, null, new Map([[2, "Поликлиника"]]));
    expect(label).toBe("Поликлиника");
  });

  it("offers no-parent option on create even when root exists", () => {
    expect(
      canOfferNoParentOption({
        mode: "create",
        rootExists: true,
        activeUnit: null,
      }),
    ).toBe(true);
  });

  it("offers no-parent option only for existing root in edit mode", () => {
    expect(
      canOfferNoParentOption({
        mode: "edit",
        rootExists: true,
        activeUnit: { unit_id: 10, parent_unit_id: null, name: "Root", is_active: true },
      }),
    ).toBe(true);
    expect(
      canOfferNoParentOption({
        mode: "edit",
        rootExists: true,
        activeUnit: { unit_id: 11, parent_unit_id: 10, name: "Child", is_active: true },
      }),
    ).toBe(false);
  });
});
