import { describe, expect, it, vi } from "vitest";

import { apiFetchJson } from "@/lib/api";

import { getPersonnelOrderTemplatePublished, previewPersonnelOrderTemplateDraft, previewSavedPersonnelOrderTemplateDraft, savePersonnelOrderTemplateDraft, type PersonnelOrderTemplateDraft, type PersonnelOrderTemplateDraftText } from "./personnelOrderTemplatesApi.client";

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

it("requests the exact saved draft identity and rejects a different preview version", async () => {
  const saved = { ...draft, template_id: 101, template_version_id: 1327, revision: 1, item_type_code: "RETURN_FROM_CHILDCARE_LEAVE" } as PersonnelOrderTemplateDraft;
  vi.mocked(apiFetchJson).mockResolvedValueOnce({ template_id: 101, template_version_id: 1327, revision: 1, previews: {} });
  await previewSavedPersonnelOrderTemplateDraft(saved);
  expect(apiFetchJson).toHaveBeenCalledWith("/admin/personnel-order-templates/RETURN_FROM_CHILDCARE_LEAVE/draft/preview?template_id=101&expected_revision=1");
  vi.mocked(apiFetchJson).mockResolvedValueOnce({ template_id: 101, template_version_id: 1328, revision: 1, previews: {} });
  await expect(previewSavedPersonnelOrderTemplateDraft(saved)).rejects.toThrow("Версия предварительного просмотра");
});

describe("savePersonnelOrderTemplateDraft", () => {
  it("sends only the eight editable fields and optimistic-lock revision", async () => {
    vi.mocked(apiFetchJson).mockResolvedValueOnce({});
    const draftWithMetadata: PersonnelOrderTemplateDraft = {
      ...draft,
      template_version_id: 17,
      item_type_code: "LEAVE.UNPAID.GRANT",
      version_number: 4,
      status: "DRAFT",
      revision: 9,
      based_on_built_in: true,
    };

    await savePersonnelOrderTemplateDraft("LEAVE.UNPAID.GRANT", { ...draftWithMetadata, expected_revision: 9 });

    expect(apiFetchJson).toHaveBeenCalledWith(
      "/admin/personnel-order-templates/LEAVE.UNPAID.GRANT/draft",
      { method: "PUT", body: { ...draft, expected_revision: 9 } },
    );
  });
});

describe("getPersonnelOrderTemplatePublished", () => {
  it("uses the read-only GET endpoint", async () => {
    vi.mocked(apiFetchJson).mockResolvedValueOnce(null);

    await getPersonnelOrderTemplatePublished("TERMINATION");

    expect(apiFetchJson).toHaveBeenCalledWith("/admin/personnel-order-templates/TERMINATION/published");
  });
});
