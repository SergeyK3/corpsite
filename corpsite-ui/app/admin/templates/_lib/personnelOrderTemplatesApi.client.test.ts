import { describe, expect, it, vi } from "vitest";

import { apiFetchJson } from "@/lib/api";

import { previewPersonnelOrderTemplateDraft, type PersonnelOrderTemplateDraftText } from "./personnelOrderTemplatesApi.client";

vi.mock("@/lib/api", () => ({ apiFetchJson: vi.fn() }));

const draft: PersonnelOrderTemplateDraftText = {
  title_ru: "Заголовок", title_kk: "Тақырып",
  preamble_ru: "Преамбула", preamble_kk: "Кіріспе",
  body_template_ru: "{{employee.full_name}}", body_template_kk: "{{employee.full_name}}",
  basis_template_ru: "Основание", basis_template_kk: "Негіз",
};

describe("previewPersonnelOrderTemplateDraft", () => {
  it("sends the complete typed draft object rather than a pre-serialized JSON string", async () => {
    vi.mocked(apiFetchJson).mockResolvedValueOnce({ previews: {} });

    await previewPersonnelOrderTemplateDraft("LEAVE.UNPAID.GRANT", draft);

    expect(apiFetchJson).toHaveBeenCalledWith(
      "/admin/personnel-order-templates/LEAVE.UNPAID.GRANT/draft/preview",
      { method: "POST", body: draft },
    );
  });
});
