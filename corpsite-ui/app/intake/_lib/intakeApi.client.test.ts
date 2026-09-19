import { describe, expect, it } from "vitest";

import { emptyIntakeDraftPayload, mapIntakeApiError, toCanonicalIntakeV2, toIntakeFormPayload, type IntakeDraftPayload } from "./intakeApi.client";

function tokenError(code: string) {
  return { status: 403, details: { detail: { code, message: "internal detail" } } };
}

describe("mapIntakeApiError", () => {
  it("shows a clear message for an expired link", () => {
    expect(mapIntakeApiError(tokenError("TOKEN_EXPIRED"), "Не удалось открыть анкету")).toContain(
      "Срок действия ссылки истёк",
    );
  });

  it("does not expose backend details for a damaged link", () => {
    const message = mapIntakeApiError(tokenError("TOKEN_INVALID"), "Не удалось открыть анкету");

    expect(message).toContain("Ссылка недействительна");
    expect(message).not.toContain("internal detail");
  });
});

describe("canonical payload form adapter", () => {
  it("opens a v2 payload with null optional values across all intake sections", () => {
    const payload = {
      schema_version: 2,
      personal: { last_name: null, first_name: null, middle_name: null, birth_date: null, birth_place: null, gender: null, citizenship: null, nationality: null, photo_file_id: null },
      contacts: { email: null, mobile_phone: null, residence_address: null, registration_address: null },
      military: { status: "not_provided", rank: null, category: null, composition: null, commissariat: null, specialty_code: null, specialty_name: null, fitness_category: null, registration_group: null, registration_category: null },
      education: [{ record_id: "a", start_date: null, end_date: null, institution_original: null, document_number: null }],
      employment_biography: [{ record_id: "b", start_date: null, end_date: null, organization_original: null, position_original: null, reason_for_leaving: null }],
      relatives: [{ record_id: "c", relationship: "жена", relationship_other: null, full_name: null, birth_date: null, workplace: null }],
      training: [{ record_id: "d", start_date: null, end_date: null, course_name_original: null, institution_original: null, hours: 840, hours_is_manual: false }],
      additional: { foreign_languages: [], awards: [], academic_degrees: [], academic_titles: [] }, current_step: "personal",
    } as unknown as IntakeDraftPayload;

    const form = toIntakeFormPayload(payload) as unknown as {
      contacts: Record<string, unknown>; military: Record<string, unknown>; education: Array<Record<string, unknown>>;
      employment_biography: Array<Record<string, unknown>>; relatives: Array<Record<string, unknown>>; training: Array<Record<string, unknown>>;
    };
    expect(form.contacts.email).toBe("");
    expect(form.military.rank).toBe("");
    expect(form.education[0].start_date).toBe("");
    expect(form.employment_biography[0].end_date).toBe("");
    expect(form.relatives[0].birth_year).toBe("");
    expect(form.training[0].hours).toBe(840);
    expect(form.training[0].hours_is_manual).toBe(false);
  });

  it("serializes an edited relative using v2 names and keeps its record id", () => {
    const source = toIntakeFormPayload({
      ...emptyIntakeDraftPayload(),
      relatives: [{ record_id: "a0ed72da-6ccf-4ef2-8d4a-3bb2c9097c08", relationship: "жена", relationship_other: null, full_name: "Садыкова Айгерим Туржановна", birth_date: "1996-11-21", workplace: "домохозяйка" }],
    } as IntakeDraftPayload);
    const payload = source;
    const canonical = toCanonicalIntakeV2(payload) as { relatives: Array<Record<string, unknown>> };
    expect(canonical.relatives[0]).toMatchObject({ record_id: "a0ed72da-6ccf-4ef2-8d4a-3bb2c9097c08", birth_date: "1996-11-21", workplace: "домохозяйка" });
    expect(canonical.relatives[0]).not.toHaveProperty("birth_year");
    expect(canonical.relatives[0]).not.toHaveProperty("work_place");
  });
});
