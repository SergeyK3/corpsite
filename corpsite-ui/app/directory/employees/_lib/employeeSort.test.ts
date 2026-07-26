import { describe, expect, it } from "vitest";

import {
  isEmployeeSortColumn,
  parseSortOrder,
  sortIndicator,
  toggleEmployeeSort,
} from "./employeeSort";

describe("employeeSort", () => {
  it("starts ascending when switching to a new column", () => {
    expect(toggleEmployeeSort({ sort: "fio", order: "desc" }, "position")).toEqual({
      sort: "position",
      order: "asc",
    });
  });

  it("toggles direction when clicking the active column", () => {
    expect(toggleEmployeeSort({ sort: "fio", order: "asc" }, "fio")).toEqual({
      sort: "fio",
      order: "desc",
    });
    expect(toggleEmployeeSort({ sort: "rate", order: "desc" }, "rate")).toEqual({
      sort: "rate",
      order: "asc",
    });
  });

  it("validates sort column and order params", () => {
    expect(isEmployeeSortColumn("status")).toBe(true);
    expect(isEmployeeSortColumn("unknown")).toBe(false);
    expect(parseSortOrder("asc")).toBe("asc");
    expect(parseSortOrder("desc")).toBe("desc");
    expect(parseSortOrder("up")).toBeUndefined();
  });

  it("renders sort direction indicators", () => {
    expect(sortIndicator("asc")).toBe("↑");
    expect(sortIndicator("desc")).toBe("↓");
  });
});
