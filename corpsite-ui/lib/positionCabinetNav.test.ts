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
  it("lists tasks, dashboards, and the personal-card section", () => {
    expect(POSITION_CABINET_NAV_ITEMS.map((item) => item.id)).toEqual([
      "tasks",
      "dashboards",
      "personal_card",
      "orders",
    ]);
    expect(POSITION_CABINET_NAV_ITEMS.map((item) => item.label)).toEqual([
      "Мои задачи",
      "Дашборды",
      "Личная карточка",
      "Приказы",
    ]);
    expect(POSITION_CABINET_NAV_ITEMS.map((item) => item.title)).toEqual([
      "Мои задачи",
      "Дашборды",
      "Личная карточка",
      "Приказы",
    ]);
    expect(POSITION_CABINET_TAB_LABELS).toEqual({
      tasks: "Мои задачи",
      dashboards: "Дашборды",
      personal_card: "Личная карточка",
      orders: "Приказы",
    });
    expect(getPositionCabinetTabLabel("dashboards")).toBe("Дашборды");
    expect(getPositionCabinetTabLabel("personal_card")).toBe("Личная карточка");
    expect(getPositionCabinetTabLabel("orders")).toBe("Приказы");
  });

  it("detects position cabinet routes", () => {
    expect(isPositionCabinetRoute("/tasks")).toBe(true);
    expect(isPositionCabinetRoute("/tasks?task_id=1")).toBe(false);
    expect(isPositionCabinetRoute("/dashboards")).toBe(true);
    expect(isPositionCabinetRoute("/profile/personal-card")).toBe(true);
    expect(isPositionCabinetRoute("/education")).toBe(false);
    expect(isPositionCabinetRoute("/profile")).toBe(false);
    expect(isPositionCabinetRoute("/directory/personnel/orders")).toBe(false);
  });

  it("shouldShowPositionCabinetNav keeps HR routes out of active tab semantics", () => {
    expect(shouldShowPositionCabinetNav("/tasks", { showPersonnelVisibility: false })).toBe(true);
    expect(shouldShowPositionCabinetNav("/dashboards", { showPersonnelVisibility: false })).toBe(true);
    expect(shouldShowPositionCabinetNav("/profile/personal-card", { showPersonnelVisibility: false })).toBe(true);
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
    expect(resolvePositionCabinetSection("/profile/personal-card")).toBe("personal_card");
    expect(resolvePositionCabinetSection("/profile/orders")).toBe("orders");
    expect(resolvePositionCabinetSection("/profile")).toBeNull();
  });

  it("places orders directly after the personal card", () => {
    const ids = POSITION_CABINET_NAV_ITEMS.map((item) => item.id);
    expect(ids.indexOf("orders")).toBe(ids.indexOf("personal_card") + 1);
    expect(POSITION_CABINET_NAV_ITEMS.find((item) => item.id === "orders")?.label).toBe("Приказы");
  });
});
