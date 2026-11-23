// FILE: corpsite-ui/lib/orgUnitsTree.test.ts
import { describe, expect, it } from "vitest";

import {
  buildDefaultExpandedKeys,
  collectExpandableKeys,
  flattenOrgUnits,
} from "./orgUnitsTree";

describe("flattenOrgUnits", () => {
  it("flattens nested org units with depth prefixes", () => {
    const rows = flattenOrgUnits([
      {
        unit_id: 1,
        name: "Клиника",
        children: [{ unit_id: 2, name: "Терапия", children: [] }],
      },
    ]);

    expect(rows).toEqual([
      { id: 1, label: "Клиника" },
      { id: 2, label: "— Терапия" },
    ]);
  });
});

describe("buildDefaultExpandedKeys", () => {
  const tree = [
    {
      key: "group-1",
      unit_id: null,
      children: [
        {
          key: "u-10",
          unit_id: 10,
          children: [{ key: "u-11", unit_id: 11, children: [] }],
        },
      ],
    },
    { key: "group-2", unit_id: null, children: [] },
  ];

  it("starts collapsed when nothing is selected", () => {
    expect(buildDefaultExpandedKeys(tree, null)).toEqual(new Set());
    expect(buildDefaultExpandedKeys(tree, undefined)).toEqual(new Set());
  });

  it("expands ancestors of the selected unit", () => {
    expect(buildDefaultExpandedKeys(tree, 11)).toEqual(new Set(["group-1", "u-10"]));
  });
});

describe("collectExpandableKeys", () => {
  it("returns keys of all nodes with children", () => {
    const keys = collectExpandableKeys([
      {
        key: "group-1",
        children: [{ key: "u-1", children: [] }],
      },
    ]);

    expect(keys).toEqual(["group-1"]);
  });
});
