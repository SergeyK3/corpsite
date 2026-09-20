import { describe, expect, it } from "vitest";

import { buildPersonCardPdfViewModel } from "./personCardPdfViewModel";

const ppr = {
  identity: { iin: "masked", resolved_person_id: 7 },
  general: { full_name: "Исправленная Анна", iin: "masked", birth_date: "1990-01-02" },
  sections: {
    "PPR-EDUCATION": { active: [{ education_kind: "masters", institution_name: "КазНУ", started_at: "2015", completed_at: "2017", specialty: "Право", qualification: null, diploma_number: "D-1", document_date: null }] },
    "PPR-TRAINING": { active: [] }, "PPR-EMPLOYMENT-BIOGRAPHY": { active: [] }, "PPR-MILITARY": { active: [] }, "PPR-FAMILY": { active: [] },
  },
  intended_employment: null,
  additional: { foreign_languages: [{ language: "Английский", proficiency: "Владеет свободно" }], qualification_categories: [], awards: [], academic_degrees: [], academic_titles: [], source_note_hint: null },
} as never;

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
