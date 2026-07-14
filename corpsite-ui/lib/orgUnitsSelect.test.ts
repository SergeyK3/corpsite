import { describe, expect, it } from "vitest";

import { buildOrgUnitSelectOptionsFromRows } from "./orgUnitsSelect";
import { filterOrgUnitOptionsForGroup } from "./taskOrgFilters";

const CLINICAL_GROUP_ID = 1;
const ADMIN_GROUP_ID = 2;

const groupLabelById = new Map<number, string>([
  [CLINICAL_GROUP_ID, "Клинические"],
  [ADMIN_GROUP_ID, "Административные"],
]);

describe("buildOrgUnitSelectOptionsFromRows clinical cascade regression", () => {
  const treeRows = [
    {
      id: "1",
      title: "Многопрофильный медицинский центр",
      group_id: null,
      children: [
        {
          id: "100",
          title: "Клинический корпус",
          group_id: CLINICAL_GROUP_ID,
          children: [
            {
              id: "101",
              title: "Терапевтическое отделение",
              group_id: null,
              children: [],
            },
          ],
        },
        {
          id: "200",
          title: "Отдел кадров",
          group_id: ADMIN_GROUP_ID,
          children: [],
        },
      ],
    },
  ];

  const flatRows = [
    {
      id: 1,
      unit_id: 1,
      name: "Многопрофильный медицинский центр",
      parent_unit_id: null,
      group_id: null,
    },
    {
      id: 100,
      unit_id: 100,
      name: "Клинический корпус",
      parent_unit_id: 1,
      group_id: CLINICAL_GROUP_ID,
    },
    {
      id: 101,
      unit_id: 101,
      name: "Терапевтическое отделение",
      parent_unit_id: 100,
      group_id: null,
    },
    {
      id: 200,
      unit_id: 200,
      name: "Отдел кадров",
      parent_unit_id: 1,
      group_id: ADMIN_GROUP_ID,
    },
  ];

  it("inherits group_id for nested child without own group_id", () => {
    const options = buildOrgUnitSelectOptionsFromRows(treeRows, [], groupLabelById);
    const therapy = options.find((row) => row.unit_id === 101);

    expect(therapy).toEqual({
      unit_id: 101,
      name: "Терапевтическое отделение",
      group_id: CLINICAL_GROUP_ID,
    });
  });

  it("returns non-empty clinical group filter with nested departments", () => {
    const options = buildOrgUnitSelectOptionsFromRows(treeRows, flatRows, groupLabelById);
    const clinical = filterOrgUnitOptionsForGroup(options, CLINICAL_GROUP_ID);

    expect(clinical.map((row) => row.unit_id).sort((a, b) => a - b)).toEqual([100, 101]);
    expect(clinical.some((row) => row.name.includes("Терапевтическое"))).toBe(true);
  });

  it("excludes HR department from clinical group filter", () => {
    const options = buildOrgUnitSelectOptionsFromRows(treeRows, flatRows, groupLabelById);
    const clinical = filterOrgUnitOptionsForGroup(options, CLINICAL_GROUP_ID);

    expect(clinical.some((row) => row.unit_id === 200)).toBe(false);
    expect(clinical.some((row) => row.name === "Отдел кадров")).toBe(false);
  });

  it("prefers enriched flat group_id when tree flatten had null group_id", () => {
    const treeOnlyNullChildren = [
      {
        id: "1",
        title: "Многопрофильный медицинский центр",
        group_id: null,
        children: [
          {
            id: "101",
            title: "Терапевтическое отделение",
            group_id: null,
            children: [],
          },
        ],
      },
    ];

    const options = buildOrgUnitSelectOptionsFromRows(treeOnlyNullChildren, flatRows, groupLabelById);
    const clinical = filterOrgUnitOptionsForGroup(options, CLINICAL_GROUP_ID);

    expect(clinical.some((row) => row.unit_id === 101)).toBe(true);
  });

  it("handles string group_id values in API rows", () => {
    const stringGroupTree = [
      {
        id: "100",
        title: "Клинический корпус",
        group_id: String(CLINICAL_GROUP_ID),
        children: [
          {
            id: "101",
            title: "Терапевтическое отделение",
            group_id: null,
            children: [],
          },
        ],
      },
    ];

    const options = buildOrgUnitSelectOptionsFromRows(stringGroupTree, [], groupLabelById);
    const clinical = filterOrgUnitOptionsForGroup(options, CLINICAL_GROUP_ID);

    expect(clinical.map((row) => row.unit_id).sort((a, b) => a - b)).toEqual([100, 101]);
  });

  it("matches clinical filter when selected group id is string", () => {
    const options = buildOrgUnitSelectOptionsFromRows(treeRows, flatRows, groupLabelById);
    const clinical = filterOrgUnitOptionsForGroup(options, String(CLINICAL_GROUP_ID));

    expect(clinical.length).toBeGreaterThan(0);
    expect(clinical.every((row) => row.group_id === CLINICAL_GROUP_ID)).toBe(true);
  });
});
