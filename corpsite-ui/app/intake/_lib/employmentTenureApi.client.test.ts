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
        organization_original: "A", organization_normalized: null, position_original: "", position_normalized: null,
        start_date: "01.09.1993", end_date: "25.07.1994",
      },
      {
        organization_original: "B", organization_normalized: "", position_original: "", position_normalized: "",
        start_date: "01.01.2020", end_date: null,
      },
    ]);

    expect(prepared[0]).toEqual({
      record_id: "row-a",
      organization_original: "A", organization_normalized: null, position_original: "", position_normalized: null,
      start_date: "1993-09-01", end_date: "1994-07-25",
    });
    expect(prepared[1].record_id).toBe("legacy-1");
    expect(prepared[1].start_date).toBe("2020-01-01");
    expect(prepared[1].end_date).toBeNull();
  });
});
