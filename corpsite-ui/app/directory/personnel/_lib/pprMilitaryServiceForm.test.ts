import { describe, expect, it } from "vitest";

import {
  ALLOWED_MILITARY_SERVICE_WRITE_KEYS,
  assertAllowedMilitaryServiceWritePayload,
  buildMilitaryServiceRecordPayload,
  militaryRecordToFormState,
  validateMilitaryServiceFormForSubmit,
  type MilitaryServiceFormState,
} from "./pprMilitaryServiceForm";
import {
  PPR_MILITARY_RECORD_KIND_NOT_APPLICABLE,
  PPR_MILITARY_RECORD_KIND_REGISTRATION,
} from "./pprQueryTypes";

const baseForm: MilitaryServiceFormState = {
  record_kind: PPR_MILITARY_RECORD_KIND_REGISTRATION,
  obligation_status: "liable",
  registration_category: "II",
  military_rank: "рядовой",
  military_specialty_code: "1234567",
  personnel_composition: "soldiers",
  fitness_category: "А",
  registration_status: "registered",
  commissariat_name: "Алмалинский РВК",
  registered_at: "2015-05-01",
  deregistered_at: "",
  military_id_book_series: "",
  military_id_book_number: "",
  registration_certificate_series: "",
  registration_certificate_number: "",
  notes: "",
};

describe("pprMilitaryServiceForm", () => {
  it("not_applicable omits military attribute fields", () => {
    const payload = buildMilitaryServiceRecordPayload({
      ...baseForm,
      record_kind: PPR_MILITARY_RECORD_KIND_NOT_APPLICABLE,
      notes: "",
    });

    expect(payload).toEqual({ record_kind: PPR_MILITARY_RECORD_KIND_NOT_APPLICABLE });
    expect(payload).not.toHaveProperty("military_rank");
    expect(payload).not.toHaveProperty("obligation_status");
  });

  it("not_applicable strips leftover registration and document fields after kind switch", () => {
    const payload = buildMilitaryServiceRecordPayload({
      ...baseForm,
      record_kind: PPR_MILITARY_RECORD_KIND_NOT_APPLICABLE,
      military_id_book_series: "АБ",
      military_id_book_number: "1234567",
      registration_certificate_series: "СП",
      registration_certificate_number: "999",
      notes: "Не подлежит воинскому учёту",
    });

    expect(payload).toEqual({
      record_kind: PPR_MILITARY_RECORD_KIND_NOT_APPLICABLE,
      notes: "Не подлежит воинскому учёту",
    });
    expect(payload).not.toHaveProperty("military_id_book_series");
    expect(payload).not.toHaveProperty("registration_certificate_number");
    expect(payload).not.toHaveProperty("commissariat_name");
  });

  it("registration includes only filled fields", () => {
    const payload = buildMilitaryServiceRecordPayload(baseForm);

    expect(payload).toEqual({
      record_kind: PPR_MILITARY_RECORD_KIND_REGISTRATION,
      obligation_status: "liable",
      registration_category: "II",
      military_rank: "рядовой",
      military_specialty_code: "1234567",
      personnel_composition: "soldiers",
      fitness_category: "А",
      registration_status: "registered",
      commissariat_name: "Алмалинский РВК",
      registered_at: "2015-05-01",
    });
  });

  it("registration rejects incomplete VUS number", () => {
    const result = validateMilitaryServiceFormForSubmit({
      ...baseForm,
      military_specialty_code: "123456",
    });

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.message).toMatch(/7 цифр/i);
    }
  });

  it("registration requires at least one structured field", () => {
    const result = validateMilitaryServiceFormForSubmit({
      ...baseForm,
      obligation_status: "",
      registration_category: "",
      military_rank: "   ",
      registration_status: "",
    });

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.message).toMatch(/хотя бы одно/i);
    }
  });

  it("supersede replacement uses only allowed write keys", () => {
    const payload = buildMilitaryServiceRecordPayload(baseForm);
    assertAllowedMilitaryServiceWritePayload(payload);
    for (const forbidden of ["person_id", "record_id", "lifecycle_status", "verification_status", "created_at", "updated_at"]) {
      expect(ALLOWED_MILITARY_SERVICE_WRITE_KEYS.has(forbidden)).toBe(false);
      expect(payload).not.toHaveProperty(forbidden);
    }
  });

  it("maps active military record into editable form state", () => {
    const form = militaryRecordToFormState({
      record_id: 201,
      record_kind: PPR_MILITARY_RECORD_KIND_REGISTRATION,
      obligation_status: "liable",
      registration_category: "II",
      military_rank: "Старший лейтенант",
      military_specialty_code: "1234567",
      personnel_composition: "officers",
      fitness_category: "А",
      registration_status: "registered",
      commissariat_name: "Алмалинский РВК",
      registered_at: "2015-05-01T00:00:00Z",
      deregistered_at: null,
      notes: null,
      source_type: "entered",
      provenance: null,
      metadata: null,
      employee_context_id: null,
      verification_status: "verified",
      lifecycle_status: "active",
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-02-01T00:00:00Z",
    });

    expect(form.personnel_composition).toBe("officers");
    expect(form.military_rank).toBe("Старший лейтенант");
    expect(form.obligation_status).toBe("liable");
    expect(form.registered_at).toBe("2015-05-01");
  });
});
