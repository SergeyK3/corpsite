import { describe, expect, it } from "vitest";

import {
  getPositionCabinetTabLabel,
  isPositionCabinetRoute,
  POSITION_CABINET_NAV_ITEMS,
  POSITION_CABINET_TAB_LABELS,
  resolvePositionCabinetSection,
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
  });

  it("resolves active section from pathname", () => {
    expect(resolvePositionCabinetSection("/tasks")).toBe("tasks");
    expect(resolvePositionCabinetSection("/dashboards")).toBe("dashboards");
    expect(resolvePositionCabinetSection("/education")).toBe("education");
    expect(resolvePositionCabinetSection("/profile")).toBeNull();
  });
});
