import { describe, expect, it } from "vitest";

import {
  normalizeTenureDateForApi,
  prepareEmploymentTenureRecords,
} from "./employmentTenureApi.client";

describe("employmentTenureApi.client", () => {
  it("normalizes dd.mm.yyyy to ISO without using Date parsing", () => {
    expect(normalizeTenureDateForApi("01.09.1993")).toBe("1993-09-01");
    expect(normalizeTenureDateForApi("1993-09-01")).toBe("1993-09-01");
    expect(normalizeTenureDateForApi("")).toBeNull();
    expect(normalizeTenureDateForApi("   ")).toBeNull();
  });

  it("prepares API records with record_id and normalized dates", () => {
    const prepared = prepareEmploymentTenureRecords([
      {
        record_id: "row-a",
        organization: "A",
        position: "",
        year_from: "01.09.1993",
        year_to: "25.07.1994",
        reason_for_leaving: "",
      },
      {
        organization: "B",
        position: "",
        year_from: "01.01.2020",
        year_to: "",
        reason_for_leaving: "",
      },
    ]);

    expect(prepared[0]).toEqual({
      record_id: "row-a",
      organization: "A",
      position: "",
      year_from: "1993-09-01",
      year_to: "1994-07-25",
      reason_for_leaving: "",
    });
    expect(prepared[1].record_id).toBe("legacy-1");
    expect(prepared[1].year_from).toBe("2020-01-01");
    expect(prepared[1].year_to).toBeNull();
  });
});
