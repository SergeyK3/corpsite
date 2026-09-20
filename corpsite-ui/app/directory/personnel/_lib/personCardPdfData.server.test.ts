import { afterEach, describe, expect, it, vi } from "vitest";

import { loadPersonCardPdfDocument } from "./personCardPdfData.server";

afterEach(() => vi.unstubAllGlobals());

describe("loadPersonCardPdfDocument", () => {
  it("renders the neutral current-work message when the person has no employee assignment", async () => {
    const fetchMock = vi.fn(async (input: string) => {
      if (input.includes("/photo")) return new Response(new Uint8Array([0xff, 0xd8, 1]), { status: 200 });
      if (input.includes("/contacts")) return Response.json({ canonical: { mobile_phone: "+7700", email: "corrected@example.test", registration_address: null, residence_address: null }, fallback: null });
      return Response.json({ identity: { iin: "masked", resolved_person_id: 7 }, general: { full_name: "Исправленная Анна", iin: "masked", birth_date: null }, sections: { "PPR-EDUCATION": { active: [] }, "PPR-TRAINING": { active: [] }, "PPR-EMPLOYMENT-BIOGRAPHY": { active: [] }, "PPR-MILITARY": { active: [] }, "PPR-FAMILY": { active: [] } }, intended_employment: null, additional: { foreign_languages: [], qualification_categories: [], awards: [], academic_degrees: [], academic_titles: [], source_note_hint: null } });
    });
    vi.stubGlobal("fetch", fetchMock);
    const document = await loadPersonCardPdfDocument(7, { authorizationHeader: "Bearer token", bearerToken: "token", devUserId: null, requestingUserId: "1" });
    const paths = fetchMock.mock.calls.map(([input]) => String(input));
    expect(paths).toEqual(expect.arrayContaining([expect.stringContaining("/api/ppr/persons/7"), expect.stringContaining("/contacts"), expect.stringContaining("/photo")]));
    expect(paths.some((path) => path.includes("intake") || path.includes("application"))).toBe(false);
    expect(document.html).toContain("corrected@example.test");
    expect(document.html).toContain("person-card-pdf-section-current_organization");
    expect(document.html).toContain("Сведения о работе в текущей организации пока не сформированы");
    expect(document.html).not.toContain("tenure_calculation");
  });

  it("loads the active operational assignment from the Person-scoped projection", async () => {
    const fetchMock = vi.fn(async (input: string) => {
      if (input.includes("/photo")) return new Response(new Uint8Array([0xff, 0xd8, 1]), { status: 200 });
      if (input.includes("/contacts")) return Response.json({ canonical: null, fallback: null });
      if (input.includes("/operational-assignment")) {
        return Response.json({
          has_assignment: true,
          department_group_name: "Администрация",
          org_unit_name: "Отдел кадров",
          position_name: "Специалист",
          status: "Зачислен",
          employment_rate: "1",
        });
      }
      return Response.json({
        identity: { iin: "masked", resolved_person_id: 7, employee_context_id: null },
        general: { full_name: "Анна", iin: "masked", birth_date: null },
        sections: { "PPR-EDUCATION": { active: [] }, "PPR-TRAINING": { active: [] }, "PPR-EMPLOYMENT-BIOGRAPHY": { active: [] }, "PPR-MILITARY": { active: [] }, "PPR-FAMILY": { active: [] } },
        intended_employment: { org_group_name: "Черновик", org_unit_name: "Черновик", position_name: "Черновик", employment_rate: 2 },
        additional: { foreign_languages: [], qualification_categories: [], awards: [], academic_degrees: [], academic_titles: [], source_note_hint: null },
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const document = await loadPersonCardPdfDocument(7, { authorizationHeader: "Bearer token", bearerToken: "token", devUserId: null, requestingUserId: "1" });
    const paths = fetchMock.mock.calls.map(([input]) => String(input));
    expect(paths).toEqual(expect.arrayContaining([
      expect.stringContaining("/api/ppr/persons/7/operational-assignment"),
    ]));
    expect(document.html).toContain("Администрация");
    expect(document.html).toContain("Отдел кадров");
    expect(document.html).toContain("Специалист");
    expect(document.html).toContain("Зачислен");
    expect(document.html).not.toContain("Черновик");
  });
});
