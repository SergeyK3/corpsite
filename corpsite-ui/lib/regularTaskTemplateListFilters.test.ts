// FILE: corpsite-ui/lib/regularTaskTemplateListFilters.test.ts
import { describe, expect, it } from "vitest";

import {
  applyExecutorRoleFilterChange,
  applyGroupFilterChange,
  applyUnitFilterChange,
  buildRegularTasksListApiQuery,
  clearExecutorRoleIfNotAllowed,
  deriveExecutorRoleOptionsFromTemplates,
  EMPTY_REGULAR_TASK_TEMPLATE_LIST_FILTERS,
  hasActiveRegularTaskTemplateListFilters,
  resetRegularTaskTemplateListFilters,
  stripLegacyOrgScopeParams,
} from "./regularTaskTemplateListFilters";

const ORG_UNITS = [
  { unit_id: 44, name: "ОВЭиПД", group_id: 1 },
  { unit_id: 72, name: "Отдел экспертизы", group_id: 3 },
  { unit_id: 73, name: "Отдел кадров", group_id: 3 },
] as const;

describe("regularTaskTemplateListFilters", () => {
  it("builds API query without org scope by default", () => {
    expect(
      buildRegularTasksListApiQuery(EMPTY_REGULAR_TASK_TEMPLATE_LIST_FILTERS, {
        status: "active",
        limit: 200,
        offset: 0,
      }),
    ).toEqual({
      status: "active",
      limit: 200,
      offset: 0,
      org_group_id: undefined,
      org_unit_id: undefined,
      executor_role_id: undefined,
    });
  });

  it("passes explicit org and executor filters to API query", () => {
    expect(
      buildRegularTasksListApiQuery(
        { org_group_id: 3, org_unit_id: 73, executor_role_id: 14 },
        { status: "active", limit: 50, offset: 0 },
      ),
    ).toEqual({
      status: "active",
      limit: 50,
      offset: 0,
      org_group_id: 3,
      org_unit_id: 73,
      executor_role_id: 14,
    });
  });

  it("detects active filters and resets them", () => {
    expect(hasActiveRegularTaskTemplateListFilters({})).toBe(false);
    expect(hasActiveRegularTaskTemplateListFilters({ org_group_id: 3 })).toBe(true);
    expect(hasActiveRegularTaskTemplateListFilters({ executor_role_id: 14 })).toBe(true);
    expect(resetRegularTaskTemplateListFilters()).toEqual({});
  });

  it("links group to unit options and clears unit when group is cleared", () => {
    const withGroup = applyGroupFilterChange(
      { org_group_id: 3, org_unit_id: 73 },
      1,
      ORG_UNITS,
    );
    expect(withGroup).toEqual({ org_group_id: 1 });

    const cleared = applyGroupFilterChange(
      { org_group_id: 3, org_unit_id: 73, executor_role_id: 14 },
      null,
      ORG_UNITS,
      [{ role_id: 14, name: "HR_HEAD", code: "HR_HEAD" }],
    );
    expect(cleared).toEqual({ executor_role_id: 14 });
  });

  it("clears executor role when it is not allowed in scoped options", () => {
    const allowed = [{ role_id: 14, name: "HR_HEAD", code: "HR_HEAD" }];
    expect(
      applyUnitFilterChange({ org_unit_id: 73, executor_role_id: 99 }, 73, allowed),
    ).toEqual({ org_unit_id: 73 });
    expect(
      clearExecutorRoleIfNotAllowed({ executor_role_id: 99 }, allowed),
    ).toEqual({});
  });

  it("derives unique executor roles from templates", () => {
    expect(
      deriveExecutorRoleOptionsFromTemplates([
        {
          executor_role_id: 14,
          executor_role_name: "HR_HEAD",
          executor_role_code: "HR_HEAD",
        },
        {
          executor_role_id: 14,
          executor_role_name: "HR_HEAD",
          executor_role_code: "HR_HEAD",
        },
        {
          executor_role_id: 7,
          executor_role_name: "Buyer",
          executor_role_code: "BUYER",
        },
      ]),
    ).toEqual([
      { role_id: 7, name: "Buyer", code: "BUYER" },
      { role_id: 14, name: "HR_HEAD", code: "HR_HEAD" },
    ]);
  });

  it("keeps unit when it belongs to the selected group", () => {
    const next = applyGroupFilterChange({ org_unit_id: 73 }, 3, ORG_UNITS);
    expect(next).toEqual({ org_group_id: 3, org_unit_id: 73 });
  });

  it("applies unit and executor role changes independently", () => {
    expect(applyUnitFilterChange({}, 73)).toEqual({ org_unit_id: 73 });
    expect(applyUnitFilterChange({ org_unit_id: 73 }, null)).toEqual({});
    expect(applyExecutorRoleFilterChange({}, 14)).toEqual({ executor_role_id: 14 });
    expect(applyExecutorRoleFilterChange({ executor_role_id: 14 }, null)).toEqual({});
  });

  it("strips legacy org scope params from URL", () => {
    const params = new URLSearchParams("org_group_id=1&org_unit_id=44&tab=runs");
    expect(stripLegacyOrgScopeParams(params)).toBe(true);
    expect(params.toString()).toBe("tab=runs");

    const unchanged = new URLSearchParams("tab=runs");
    expect(stripLegacyOrgScopeParams(unchanged)).toBe(false);
  });
});
