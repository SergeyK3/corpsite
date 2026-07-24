import { describe, expect, it } from "vitest";

import { buildEducationReconciliationSectionPayload } from "./personnelApplicationsApi.client";

describe("buildEducationReconciliationSectionPayload", () => {
  const records = [
    {
      education_type: "basic",
      institution: "КазНУ",
      year_from: "2015-09-01",
      year_to: "2019-06-30",
    },
  ];

  it("wraps array payload as records list", () => {
    expect(buildEducationReconciliationSectionPayload(records)).toEqual({ records });
  });

  it("uses records key when present", () => {
    expect(buildEducationReconciliationSectionPayload({ records })).toEqual({ records });
  });

  it("uses education key when present", () => {
    expect(buildEducationReconciliationSectionPayload({ education: records })).toEqual({ records });
  });

  it("wraps single education object as one-element records list", () => {
    const single = {
      education_type: "basic",
      institution: "Медуни",
      year_from: "1987-09-01",
      year_to: "1993-06-30",
      specialty: "Лечебное дело",
      qualification: "Врач",
      document_type: "diploma",
      diploma_number: "123",
    };
    expect(buildEducationReconciliationSectionPayload(single)).toEqual({ records: [single] });
  });

  it("returns empty records for empty object", () => {
    expect(buildEducationReconciliationSectionPayload({})).toEqual({ records: [] });
  });
});
