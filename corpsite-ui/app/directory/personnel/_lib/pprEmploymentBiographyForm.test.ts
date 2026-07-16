import { describe, expect, it } from "vitest";

import {
  ALLOWED_EXTERNAL_EMPLOYMENT_WRITE_KEYS,
  assertAllowedExternalEmploymentWritePayload,
  buildExternalEmploymentRecordPayload,
  validateExternalEmploymentFormForSubmit,
  type EmploymentBiographyFormState,
} from "./pprEmploymentBiographyForm";
import {
  PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_ATTESTATION_NONE,
  PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
  PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_NARRATIVE_SUMMARY,
} from "./pprQueryTypes";

const baseForm: EmploymentBiographyFormState = {
  record_kind: PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
  employer_name: "Employer",
  department_name: "Dept",
  position_title: "Role",
  started_at: "2018-01-01",
  ended_at: "2019-01-01",
  notes: "leftover notes",
};

describe("pprEmploymentBiographyForm", () => {
  it("attestation_none omits employer, position and date fields", () => {
    const payload = buildExternalEmploymentRecordPayload({
      ...baseForm,
      record_kind: PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_ATTESTATION_NONE,
      notes: "",
    });

    expect(payload).toEqual({ record_kind: PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_ATTESTATION_NONE });
    expect(payload).not.toHaveProperty("employer_name");
    expect(payload).not.toHaveProperty("position_title");
    expect(payload).not.toHaveProperty("started_at");
    expect(payload).not.toHaveProperty("ended_at");
  });

  it("attestation_none may include optional notes only", () => {
    const payload = buildExternalEmploymentRecordPayload({
      ...baseForm,
      record_kind: PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_ATTESTATION_NONE,
      notes: "Стаж отсутствует",
    });

    expect(payload).toEqual({
      record_kind: PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_ATTESTATION_NONE,
      notes: "Стаж отсутствует",
    });
  });

  it("narrative_summary requires notes before submit", () => {
    const result = validateExternalEmploymentFormForSubmit({
      ...baseForm,
      record_kind: PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_NARRATIVE_SUMMARY,
      notes: "   ",
    });

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.message).toMatch(/текст сводной/i);
    }
  });

  it("supersede replacement uses only allowed write keys", () => {
    const payload = buildExternalEmploymentRecordPayload({
      ...baseForm,
      record_kind: PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
    });

    assertAllowedExternalEmploymentWritePayload(payload);
    for (const forbidden of ["person_id", "record_id", "lifecycle_status", "verification_status", "created_at", "updated_at"]) {
      expect(ALLOWED_EXTERNAL_EMPLOYMENT_WRITE_KEYS.has(forbidden)).toBe(false);
      expect(payload).not.toHaveProperty(forbidden);
    }
  });
});
