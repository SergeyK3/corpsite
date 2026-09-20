import { afterEach, describe, expect, it, vi } from "vitest";

import { loadSelfPersonCardPdfDocument } from "./selfPersonCardPdfData.server";

afterEach(() => vi.unstubAllGlobals());

const auth = {
  authorizationHeader: "Bearer token",
  bearerToken: "token",
  devUserId: null,
  requestingUserId: "1",
};

describe("loadSelfPersonCardPdfDocument", () => {
  it("uses only ID-free self endpoints and adds the own operational assignment", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).includes("/operational-assignment")) {
        return Response.json({ status: "READY", operational_assignment: { department_group_name: "Administration", org_unit_name: "Human resources", position_name: "Specialist", operational_status: "active", employment_rate: 1, iin: "990101123456" } });
      }
      return Response.json({
      status: "READY",
      card: {
        general: { full_name: "Иванов Иван", iin: "********1234", birth_date: "1990-01-01" },
        sections: {
          "PPR-EDUCATION": { active: [] }, "PPR-TRAINING": { active: [] },
          "PPR-EMPLOYMENT-BIOGRAPHY": { active: [] }, "PPR-MILITARY": { active: [] }, "PPR-FAMILY": { active: [] },
        },
        additional: { foreign_languages: [], qualification_categories: [], awards: [], academic_degrees: [], academic_titles: [], source_note_hint: null },
      },
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const document = await loadSelfPersonCardPdfDocument(auth);

    const paths = fetchMock.mock.calls.map(([input]) => String(input));
    expect(paths).toEqual([
      expect.stringContaining("/api/ppr/me"),
      expect.stringContaining("/api/ppr/me/operational-assignment"),
    ]);
    expect(paths.join(" ")).not.toMatch(/persons|employees|intake|application|person_id|employee_id/);
    expect(document.filename).toBe("personal-card.pdf");
    expect(document.html).toContain("990101123456");
    expect(document.html).toContain("Human resources");
    expect(document.html).toContain("Работает");
    expect(document.html).toContain("1.00");
    expect(document.html).not.toContain(">active<");
    expect(document.html).not.toContain("tenure_calculation");
  });

  it("returns a controlled no-card result without rendering", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json({ status: "PERSON_NOT_LINKED", card: null })));

    await expect(loadSelfPersonCardPdfDocument(auth)).rejects.toMatchObject({
      status: 409,
      code: "PERSON_NOT_LINKED",
    });
  });
});
