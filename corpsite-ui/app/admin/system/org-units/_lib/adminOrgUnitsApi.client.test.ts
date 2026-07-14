import { describe, expect, it } from "vitest";

import {
  buildBulkDeleteResultRows,
  canOfferNoParentOption,
  DEPENDENCY_DISPLAY_ORDER,
  DEPENDENCY_LABELS,
  dependencyLabel,
  formatDependencyList,
  isSingleRootInvariantDetail,
  mapAdminOrgUnitsApiError,
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

  it("builds structured bulk delete rows", () => {
    const rows = buildBulkDeleteResultRows(
      [
        { unit_id: 1, ok: true },
        { unit_id: 2, ok: false, error_code: "ORG_UNIT_HAS_DEPENDENCIES", dependencies: { users: 1 } },
      ],
      new Map([
        [1, "Отдел A"],
        [2, "Отдел B"],
      ]),
    );
    expect(rows.deleted).toHaveLength(1);
    expect(rows.deleted[0].name).toBe("Отдел A");
    expect(rows.failed[0].name).toBe("Отдел B");
  });

  it("resolves group label from catalog fallback", () => {
    const label = resolveGroupLabel(2, null, new Map([[2, "Поликлиника"]]));
    expect(label).toBe("Поликлиника");
  });

  it("does not offer no-parent option on create when root exists", () => {
    expect(
      canOfferNoParentOption({
        mode: "create",
        rootExists: true,
        activeUnit: null,
      }),
    ).toBe(false);
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
