import { describe, expect, it } from "vitest";

import {
  formatDocumentDateForDisplay,
  normalizeDocumentDateInput,
  validateDocumentDate,
  validateEditableProfile,
} from "./importProfileEditor";
import type { ImportProfile } from "./importApi.client";

function baseProfile(): ImportProfile {
  return {
    basic: {
      full_name: "",
      iin: "",
      birth_date: "",
      sex: "",
      department_source: "",
      position_raw: "",
      employment_rate: null,
      nationality: "",
      phone_raw: "",
      qualification_raw: "",
    },
    education: { basic: [] },
    education_records: [],
    training_records: [],
    category_records: [],
    certificate_records: [],
    award_records: [],
    degrees: { candidate_medical_sciences: false, doctor_medical_sciences: false, raw_text: "", records: [] },
    notes_raw: "",
    status: "",
    review_status: "",
  };
}

describe("importProfileEditor document dates", () => {
  it("does not invent 01.01 for year-only category dates", () => {
    expect(normalizeDocumentDateInput("2018")).toBe("2018");
    expect(formatDocumentDateForDisplay("2018")).toBe("2018 (уточните дату)");
  });

  it("normalizes full certificate dates to ISO", () => {
    expect(normalizeDocumentDateInput("15.03.2018")).toBe("2018-03-15");
    expect(formatDocumentDateForDisplay("2018-03-15")).toBe("15.03.2018");
  });

  it("blocks profile save when category date is incomplete", () => {
    const profile = baseProfile();
    profile.category_records = [
      {
        category: "Первая",
        specialty: "Терапия",
        issued_at: "2018",
        source_field: "profile_override",
        source_text: "",
        confidence: 1,
        parse_method: "manual_override",
        document_id: null,
      },
    ];
    const errors = validateEditableProfile(profile);
    expect(errors.some((error) => error.includes("Категория"))).toBe(true);
  });

  it("accepts full certificate issue and valid_until dates", () => {
    const profile = baseProfile();
    profile.certificate_records = [
      {
        kind: "Удостоверение",
        topic: "Охрана труда",
        specialty: "Охрана труда",
        issued_at: "2018-03-15",
        valid_until: "2023-03-15",
        hours: 36,
        link: "",
        certificate_number: "",
        source_field: "profile_override",
        source_text: "",
        confidence: 1,
        parse_method: "manual_override",
        document_id: null,
      },
    ];
    expect(validateDocumentDate("15.03.2018")).toBeNull();
    expect(validateEditableProfile(profile)).toEqual([]);
  });

  it("does not invent 01.01 for year-only education dates", () => {
    expect(normalizeDocumentDateInput("2010")).toBe("2010");
    expect(formatDocumentDateForDisplay("2010")).toBe("2010 (уточните дату)");
  });

  it("blocks profile save when education date is incomplete", () => {
    const profile = baseProfile();
    profile.education_records = [
      {
        institution: "КазНМУ",
        specialty: "Лечебное дело",
        completed_at: "2010",
        record_type: "basic",
        source_field: "profile_override",
        source_text: "",
        confidence: 1,
        parse_method: "manual_override",
        document_id: null,
      },
    ];
    profile.education = { basic: profile.education_records };
    const errors = validateEditableProfile(profile);
    expect(errors.some((error) => error.includes("Учебное заведение"))).toBe(true);
  });

  it("blocks profile save when training or degree dates are incomplete", () => {
    const profile = baseProfile();
    profile.training_records = [
      {
        title: "Курс",
        organization: "Org",
        completed_at: "2020",
        hours: 36,
        started_at: "",
        source_field: "profile_override",
        source_text: "",
        confidence: 1,
        parse_method: "manual_override",
        document_id: null,
      },
    ];
    profile.degrees = {
      candidate_medical_sciences: true,
      doctor_medical_sciences: false,
      raw_text: "Кандидат медицинских наук",
      records: [
        {
          label: "Кандидат медицинских наук",
          completed_at: "2015",
          degree_type: "candidate_medical_sciences",
          source_field: "profile_override",
          source_text: "",
          confidence: 1,
          parse_method: "manual_override",
          document_id: null,
        },
      ],
    };
    const errors = validateEditableProfile(profile);
    expect(errors.some((error) => error.includes("Повышение квалификации"))).toBe(true);
    expect(errors.some((error) => error.includes("Степень"))).toBe(true);
  });
});
