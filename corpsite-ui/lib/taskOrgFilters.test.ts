import { describe, expect, it } from "vitest";

import {
  buildTaskOrgFiltersResetUrl,
  filterOrgUnitOptionsForGroup,
  hasActiveTaskOrgFilters,
  isOrgUnitAllowedForGroup,
  isPositionAllowedInOptions,
  normalizePositionOptions,
  readTaskOrgFiltersFromSearchParams,
  shouldShowTaskOrgFilters,
} from "./taskOrgFilters";

describe("readTaskOrgFiltersFromSearchParams", () => {
  it("reads org scope and position_id from query string", () => {
    const sp = new URLSearchParams("org_group_id=2&org_unit_id=15&position_id=7");
    expect(readTaskOrgFiltersFromSearchParams(sp)).toEqual({
      org_group_id: 2,
      org_unit_id: 15,
      position_id: 7,
    });
  });
});

describe("hasActiveTaskOrgFilters", () => {
  it("returns false for empty state", () => {
    expect(hasActiveTaskOrgFilters({})).toBe(false);
  });

  it("returns true when any filter is set", () => {
    expect(hasActiveTaskOrgFilters({ org_group_id: 1 })).toBe(true);
    expect(hasActiveTaskOrgFilters({ org_unit_id: 5 })).toBe(true);
    expect(hasActiveTaskOrgFilters({ position_id: 3 })).toBe(true);
  });
});

describe("shouldShowTaskOrgFilters", () => {
  it("shows filters only for system admin in team scope", () => {
    expect(
      shouldShowTaskOrgFilters({ isSystemAdmin: true, taskScope: "team" }),
    ).toBe(true);
    expect(
      shouldShowTaskOrgFilters({ isSystemAdmin: true, taskScope: "mine" }),
    ).toBe(false);
  });

  it("hides filters for managers and deputies with team scope", () => {
    expect(
      shouldShowTaskOrgFilters({ isSystemAdmin: false, taskScope: "team" }),
    ).toBe(false);
    expect(
      shouldShowTaskOrgFilters({ isSystemAdmin: false, taskScope: "mine" }),
    ).toBe(false);
  });
});

describe("interconnected org filter helpers", () => {
  const units = [
    { unit_id: 10, name: "A", group_id: 1 },
    { unit_id: 11, name: "B", group_id: 2 },
  ];

  it("limits departments to selected group", () => {
    expect(filterOrgUnitOptionsForGroup(units, 1)).toEqual([units[0]]);
  });

  it("rejects org unit outside selected group", () => {
    expect(isOrgUnitAllowedForGroup(11, 1, units)).toBe(false);
    expect(isOrgUnitAllowedForGroup(10, 1, units)).toBe(true);
  });

  it("rejects position outside available options", () => {
    const positions = [{ id: 5, label: "Врач" }];
    expect(isPositionAllowedInOptions(5, positions)).toBe(true);
    expect(isPositionAllowedInOptions(9, positions)).toBe(false);
  });
});

describe("normalizePositionOptions", () => {
  it("deduplicates and sorts positions", () => {
    expect(
      normalizePositionOptions([
        { position_id: 2, name: "Экономист" },
        { id: 1, name: "Врач" },
        { position_id: 2, name: "Экономист" },
      ]),
    ).toEqual([
      { id: 1, label: "Врач" },
      { id: 2, label: "Экономист" },
    ]);
  });
});

describe("buildTaskOrgFiltersResetUrl", () => {
  it("clears org filters and pagination offset", () => {
    const url = buildTaskOrgFiltersResetUrl(
      "/tasks",
      new URLSearchParams("org_group_id=1&org_unit_id=5&position_id=3&offset=50&status_filter=active"),
    );
    expect(url).toBe("/tasks?status_filter=active");
  });
});
