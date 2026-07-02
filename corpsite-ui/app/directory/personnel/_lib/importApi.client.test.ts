import { describe, expect, it } from "vitest";

import {
  parseGroupFilterValue,
  resolveGroupIdFromOptions,
  type DepartmentRecodingOptions,
} from "./importApi.client";

const SAMPLE_OPTIONS: DepartmentRecodingOptions = {
  groups: [
    {
      value: "clinical",
      label: "Клинические",
      group_id: 1,
      effective_log_group: "clinical",
      effective_log_group_name: "Клинические",
    },
    {
      value: "paraclinical",
      label: "Параклинические",
      group_id: 2,
      effective_log_group: "paraclinical",
      effective_log_group_name: "Параклинические",
    },
    {
      value: "admin_household",
      label: "Административно-хозяйственные",
      group_id: 3,
      effective_log_group: "admin_household",
      effective_log_group_name: "Административно-хозяйственные",
    },
  ],
  departments: [],
};

describe("importApi.client group filters", () => {
  it("parseGroupFilterValue uses slug for effective_log_group", () => {
    expect(parseGroupFilterValue("clinical")).toEqual({ effective_log_group: "clinical" });
    expect(parseGroupFilterValue("admin_household")).toEqual({ effective_log_group: "admin_household" });
  });

  it("parseGroupFilterValue keeps legacy numeric org_group_id", () => {
    expect(parseGroupFilterValue("2")).toEqual({ org_group_id: 2 });
  });

  it("resolveGroupIdFromOptions maps slug to group_id", () => {
    expect(resolveGroupIdFromOptions(SAMPLE_OPTIONS, "paraclinical")).toBe(2);
    expect(resolveGroupIdFromOptions(SAMPLE_OPTIONS, "3")).toBe(3);
  });
});
