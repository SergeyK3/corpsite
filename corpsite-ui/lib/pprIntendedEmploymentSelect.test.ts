import { describe, expect, it } from "vitest";

import {
  ensureOrgUnitInOptions,
  ensurePositionInGroups,
} from "./pprIntendedEmploymentSelect";
import {
  isOrgUnitAllowedForGroup,
  isPositionAllowedInOptions,
  flattenPersonnelOrderPositionGroups,
} from "./taskOrgFilters";

describe("ensureOrgUnitInOptions", () => {
  const catalog = [
    { unit_id: 73, name: "Отдел кадров", group_id: 3 },
    { unit_id: 51, name: "Терапия", group_id: 1 },
  ];

  it("pins saved unit for display when missing from loaded options", () => {
    const result = ensureOrgUnitInOptions(catalog, 73, "Отдел кадров", 3);
    expect(result).toEqual(catalog);
  });

  it("adds historical unit for display after async load", () => {
    const filtered: typeof catalog = [];
    const result = ensureOrgUnitInOptions(filtered, 73, "Отдел кадров", 3);
    expect(result).toEqual([{ unit_id: 73, name: "Отдел кадров", group_id: 3 }]);
  });

  it("does not pin when unit name is missing", () => {
    expect(ensureOrgUnitInOptions(catalog, 99, null, 1)).toEqual(catalog);
  });

  it("pinned display row must not make invalid group/unit pass catalog validation", () => {
    const display = ensureOrgUnitInOptions(catalog, 41, "ММЦ (корень)", 1);
    expect(display.some((row) => row.unit_id === 41)).toBe(true);

    expect(isOrgUnitAllowedForGroup(41, 1, catalog)).toBe(false);
    expect(isOrgUnitAllowedForGroup(41, 1, display)).toBe(true);
  });

  it("valid saved unit passes both display pin and catalog validation", () => {
    const display = ensureOrgUnitInOptions([], 73, "Отдел кадров", 3);
    expect(isOrgUnitAllowedForGroup(73, 3, catalog)).toBe(true);
    expect(display[0]?.unit_id).toBe(73);
  });
});

describe("ensurePositionInGroups", () => {
  const groups = [
    {
      key: "allowed_in_unit" as const,
      label: "Для подразделения",
      items: [{ id: 340, label: "Архивариус МЦ" }],
    },
  ];

  it("pins saved position for display when missing from loaded groups", () => {
    const result = ensurePositionInGroups([], 340, "Архивариус МЦ");
    const flat = flattenPersonnelOrderPositionGroups(result);
    expect(flat).toEqual([{ id: 340, label: "Архивариус МЦ" }]);
  });

  it("keeps existing groups when position already present", () => {
    expect(ensurePositionInGroups(groups, 340, "Архивариус МЦ")).toEqual(groups);
  });

  it("pinned display position must not pass validation against real catalog", () => {
    const display = ensurePositionInGroups([], 999, "Удалённая должность");
    const displayFlat = flattenPersonnelOrderPositionGroups(display);
    const catalogFlat = flattenPersonnelOrderPositionGroups(groups);

    expect(isPositionAllowedInOptions(999, displayFlat)).toBe(true);
    expect(isPositionAllowedInOptions(999, catalogFlat)).toBe(false);
    expect(isPositionAllowedInOptions(340, catalogFlat)).toBe(true);
  });
});
