import { describe, expect, it } from "vitest";

import {
  getPositionCabinetTabLabel,
  isPositionCabinetRoute,
  POSITION_CABINET_NAV_ITEMS,
  POSITION_CABINET_TAB_LABELS,
  resolvePositionCabinetSection,
  shouldShowPositionCabinetNav,
} from "./positionCabinetNav";

describe("positionCabinetNav", () => {
  it("lists tasks, dashboards, and education sections", () => {
    expect(POSITION_CABINET_NAV_ITEMS.map((item) => item.id)).toEqual([
      "tasks",
      "dashboards",
      "education",
    ]);
    expect(POSITION_CABINET_NAV_ITEMS.map((item) => item.label)).toEqual([
      "Мои задачи",
      "Дашборды",
      "Образование",
    ]);
    expect(POSITION_CABINET_NAV_ITEMS.map((item) => item.title)).toEqual([
      "Мои задачи",
      "Дашборды",
      "Образование",
    ]);
    expect(POSITION_CABINET_TAB_LABELS).toEqual({
      tasks: "Мои задачи",
      dashboards: "Дашборды",
      education: "Образование",
    });
    expect(getPositionCabinetTabLabel("dashboards")).toBe("Дашборды");
    expect(getPositionCabinetTabLabel("education")).toBe("Образование");
  });

  it("detects position cabinet routes", () => {
    expect(isPositionCabinetRoute("/tasks")).toBe(true);
    expect(isPositionCabinetRoute("/tasks?task_id=1")).toBe(false);
    expect(isPositionCabinetRoute("/dashboards")).toBe(true);
    expect(isPositionCabinetRoute("/education")).toBe(true);
    expect(isPositionCabinetRoute("/profile")).toBe(false);
    expect(isPositionCabinetRoute("/directory/personnel/orders")).toBe(false);
  });

  it("shouldShowPositionCabinetNav keeps HR routes out of active tab semantics", () => {
    expect(shouldShowPositionCabinetNav("/tasks", { showPersonnelVisibility: false })).toBe(true);
    expect(shouldShowPositionCabinetNav("/dashboards", { showPersonnelVisibility: false })).toBe(true);
    expect(shouldShowPositionCabinetNav("/education", { showPersonnelVisibility: false })).toBe(true);
    expect(shouldShowPositionCabinetNav("/directory/personnel/orders", { showPersonnelVisibility: true })).toBe(
      true,
    );
    expect(shouldShowPositionCabinetNav("/directory/personnel/journal", { showPersonnelVisibility: true })).toBe(
      true,
    );
    expect(shouldShowPositionCabinetNav("/directory/personnel/orders", { showPersonnelVisibility: false })).toBe(
      false,
    );
    expect(shouldShowPositionCabinetNav("/directory/employees", { showPersonnelVisibility: true })).toBe(false);
  });

  it("shouldShowPositionCabinetNav includes operational orders for visibility users", () => {
    expect(
      shouldShowPositionCabinetNav("/directory/operational-orders", { showPersonnelVisibility: true }),
    ).toBe(true);
    expect(
      shouldShowPositionCabinetNav("/directory/operational-orders/workspaces/1", {
        showPersonnelVisibility: true,
      }),
    ).toBe(true);
    expect(
      shouldShowPositionCabinetNav("/directory/operational-orders", { showPersonnelVisibility: false }),
    ).toBe(false);
  });

  it("shouldShowPositionCabinetNav keeps operational orders out of active tab semantics", () => {
    expect(resolvePositionCabinetSection("/directory/operational-orders")).toBeNull();
    expect(resolvePositionCabinetSection("/directory/operational-orders/workspaces/1")).toBeNull();
    expect(isPositionCabinetRoute("/directory/operational-orders")).toBe(false);
  });

  it("resolves active section from pathname", () => {
    expect(resolvePositionCabinetSection("/tasks")).toBe("tasks");
    expect(resolvePositionCabinetSection("/dashboards")).toBe("dashboards");
    expect(resolvePositionCabinetSection("/education")).toBe("education");
    expect(resolvePositionCabinetSection("/profile")).toBeNull();
  });
});
