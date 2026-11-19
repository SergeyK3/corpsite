import { describe, expect, it } from "vitest";

import { buildPersonCardPdfViewModel } from "./personCardPdfViewModel";
import type { SelfCardPdfProjection } from "./personCardPdfViewModel";
import type { PprSectionRecordResponse } from "./pprQueryTypes";

const section = (section_code: string, active: PprSectionRecordResponse[] = []) => ({ section_code, active, superseded: [], voided: [] });

const ppr: SelfCardPdfProjection = {
  general: { full_name: "Исправленная Анна", last_name: "Исправленная", first_name: "Анна", middle_name: null, iin: "masked", birth_date: "1990-01-02", created_at: "2026-01-01", updated_at: "2026-01-01" },
  sections: {
    "PPR-EDUCATION": section("PPR-EDUCATION", [{ record_id: 1, education_kind: "masters", institution_type: null, institution_name: "КазНУ", started_at: "2015", completed_at: "2017", specialty: "Право", qualification: null, diploma_number: "D-1", document_date: null, verification_status: "verified", lifecycle_status: "active" }]),
    "PPR-TRAINING": section("PPR-TRAINING"), "PPR-EMPLOYMENT-BIOGRAPHY": section("PPR-EMPLOYMENT-BIOGRAPHY"), "PPR-MILITARY": section("PPR-MILITARY"), "PPR-FAMILY": section("PPR-FAMILY"),
  },
  additional: { foreign_languages: [{ language: "Английский", proficiency: "Владеет свободно" }], foreign_languages_none: false, qualification_categories: [], awards: [], awards_none: false, academic_degrees: [], academic_degrees_none: false, academic_titles: [], academic_titles_none: false, status_facts: [], source_note_hint: null },
};

describe("buildPersonCardPdfViewModel", () => {
  it("uses corrected PPR and canonical contacts without intake or tenure", () => {
    const model = buildPersonCardPdfViewModel({ personId: 7, ppr, contacts: { mobile_phone: "+7700", email: "new@example.test", registration_address: null, residence_address: null }, photoDataUrl: null, currentAssignment: null });
    expect(model.fullName).toBe("Исправленная Анна");
    expect(model.sections.find((section) => section.key === "general")?.rows).toContainEqual(["Email", "new@example.test"]);
    expect(model.sections.find((section) => section.key === "education")?.rows[0]).toContain("КазНУ");
    expect(model.sections.map((section) => section.key)).toEqual(["general", "education", "training", "qualification_category", "employment_biography", "current_organization", "military", "relatives", "foreign_languages", "note", "additional"]);
    expect(model.sections.some((section) => section.key === "tenure_calculation")).toBe(false);
  });

  it("uses the operational assignment rather than intended employment", () => {
    const model = buildPersonCardPdfViewModel({
      personId: 7,
      ppr: {
        ...ppr,
        intended_employment: {
          org_group_id: null,
          org_unit_id: null,
          position_id: null,
          org_group_name: "Не использовать",
          org_unit_name: "Не использовать",
          position_name: "Не использовать",
          employment_rate: 9,
        },
      },
      contacts: null,
      photoDataUrl: null,
      currentAssignment: {
        departmentGroupName: "Группа отделений",
        orgUnitName: "Отдел кадров",
        positionName: "Специалист",
        statusLabel: "Зачислен",
        rate: "1",
      },
    });
    const section = model.sections.find((item) => item.key === "current_organization");
    expect(section?.rows).toEqual([["Группа отделений", "Отдел кадров", "Специалист", "Зачислен", "1"]]);
    expect(section?.rows.flat().join(" ")).not.toContain("Не использовать");
  });

  it("shows the neutral message when an active operational assignment is unavailable", () => {
    const model = buildPersonCardPdfViewModel({ personId: 7, ppr, contacts: null, photoDataUrl: null, currentAssignment: null });
    const section = model.sections.find((item) => item.key === "current_organization");
    expect(section?.rows).toEqual([]);
    expect(section?.emptyMessage).toBe("Сведения о работе в текущей организации пока не сформированы");
  });
});
