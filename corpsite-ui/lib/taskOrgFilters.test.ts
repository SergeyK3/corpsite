import { describe, expect, it } from "vitest";

import {
  buildPersonnelOrderPositionSelectGroups,
  buildScopedPositionOptionsQuery,
  buildTaskOrgFiltersResetUrl,
  flattenPersonnelOrderPositionGroups,
  filterOrgUnitOptionsForGroup,
  hasActiveTaskOrgFilters,
  isOrgUnitAllowedForGroup,
  isPositionAllowedInOptions,
  normalizeOrgGroupId,
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
    expect(isOrgUnitAllowedForGroup(10, "1", units)).toBe(true);
  });

  it("normalizes string group ids during filtering", () => {
    expect(filterOrgUnitOptionsForGroup(units, "1")).toEqual([units[0]]);
    expect(normalizeOrgGroupId("2")).toBe(2);
  });

  it("rejects position outside available options", () => {
    const positions = [{ id: 5, label: "Врач" }];
    expect(isPositionAllowedInOptions(5, positions)).toBe(true);
    expect(isPositionAllowedInOptions(9, positions)).toBe(false);
    expect(isPositionAllowedInOptions("5", positions)).toBe(true);
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

  it("keeps same-name positions with different ids", () => {
    expect(
      normalizePositionOptions([
        { position_id: 10, name: "E1 Test Position" },
        { position_id: 11, name: "E1 Test Position" },
      ]),
    ).toEqual([
      { id: 10, label: "E1 Test Position" },
      { id: 11, label: "E1 Test Position" },
    ]);
  });
});

describe("buildPersonnelOrderPositionSelectGroups", () => {
  it("places scoped positions first and dedupes by position_id", () => {
    const scoped = [
      { id: 2, label: "Заведующий" },
      { id: 1, label: "Дворник" },
    ];
    const global = [
      { id: 1, label: "Дворник" },
      { id: 3, label: "Кадровый специалист" },
      { id: 4, label: "Врач" },
      { id: 5, label: "Медсестра" },
    ];

    const groups = buildPersonnelOrderPositionSelectGroups(scoped, global);
    expect(groups).toHaveLength(2);
    expect(groups[0]?.key).toBe("allowed_in_unit");
    expect(groups[0]?.items.map((row) => row.id)).toEqual([2, 1]);
    expect(groups[1]?.key).toBe("all_positions");
    expect(groups[1]?.items.map((row) => row.id)).toEqual([4, 3, 5]);
    expect(flattenPersonnelOrderPositionGroups(groups).map((row) => row.id)).toEqual([
      2, 1, 4, 3, 5,
    ]);
  });
});

describe("buildScopedPositionOptionsQuery", () => {
  it("omits org_group_id when org_unit_id is selected (Positions page parity)", () => {
    expect(
      buildScopedPositionOptionsQuery({
        org_group_id: 3,
        org_unit_id: 73,
        scope: "allowed",
      }),
    ).toEqual({
      limit: 500,
      offset: 0,
      org_unit_id: 73,
      scope: "allowed",
    });
  });

  it("keeps org_group_id when only group scope is requested", () => {
    expect(
      buildScopedPositionOptionsQuery({
        org_group_id: 3,
        scope: "allowed",
      }),
    ).toEqual({
      limit: 500,
      offset: 0,
      org_group_id: 3,
      scope: "allowed",
    });
  });

  it("matches PositionsPageClient allowed query fields for selected unit", async () => {
    const { buildPositionsListQuery } = await import(
      "@/app/directory/positions/_components/PositionsPageClient"
    );
    const positionsQuery = buildPositionsListQuery({
      orgGroupId: 3,
      orgUnitId: 73,
      positionScope: "allowed",
    });
    const scopedQuery = buildScopedPositionOptionsQuery({
      org_group_id: 3,
      org_unit_id: 73,
      scope: "allowed",
    });

    expect(scopedQuery.org_unit_id).toBe(positionsQuery.org_unit_id);
    expect(scopedQuery.scope).toBe(positionsQuery.scope);
    expect(scopedQuery.org_group_id).toBeUndefined();
    expect(positionsQuery.org_group_id).toBeUndefined();
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
