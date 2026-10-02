import { apiFetchJson } from "@/lib/api";

export type PersonnelOrderTemplateVariable = {
  code: string;
  label: string;
};

export type PersonnelOrderTemplatePreview = {
  title: string;
  preamble: string;
  directive: string;
  body: string;
  basis: string;
  footer: string;
};

export type PersonnelOrderTemplatePilotDetail = {
  required_fields: string[];
  additional_fields: string[];
  document_parts: string[];
  variables: PersonnelOrderTemplateVariable[];
  specialty_note: string;
  previews: Record<"ru" | "kk", PersonnelOrderTemplatePreview>;
};

export type PersonnelOrderTemplateCatalogItem = {
  type_code: string;
  title_ru: string;
  title_kk: string;
  source: "BUILT_IN";
  support_level: "SUPPORTED" | "PARTIAL" | "NOT_IMPLEMENTED";
  supported_locales: string[];
  uses_specialized_generator: boolean;
  is_pilot: boolean;
  editor_available: boolean;
  allowed_variables: string[];
  required_fields: string[];
  notes: string;
  pilot_detail?: PersonnelOrderTemplatePilotDetail | null;
  template_detail?: PersonnelOrderTemplatePilotDetail | null;
};

export function listPersonnelOrderTemplateCatalog() {
  return apiFetchJson<{ items: PersonnelOrderTemplateCatalogItem[] }>("/admin/personnel-order-templates");
}

export type PersonnelOrderTemplateDraft = {
  template_version_id: number; item_type_code: string; version_number: number; status: string; revision: number; based_on_built_in: boolean;
  published_at?: string | null; published_by_user_id?: number | null;
  title_ru: string; title_kk: string; preamble_ru: string; preamble_kk: string; body_template_ru: string; body_template_kk: string; basis_template_ru: string; basis_template_kk: string;
};
export type PersonnelOrderTemplateDraftText = Pick<PersonnelOrderTemplateDraft, "title_ru" | "title_kk" | "preamble_ru" | "preamble_kk" | "body_template_ru" | "body_template_kk" | "basis_template_ru" | "basis_template_kk">;
export type PersonnelOrderTemplateEditorBase = PersonnelOrderTemplateDraftText & { source: "PUBLISHED" | "INITIAL"; item_type_code: string; template_version_id: number | null; version_number: number | null; revision: number | null; };
export function editablePersonnelOrderTemplateDraftText(source: PersonnelOrderTemplateDraftText): PersonnelOrderTemplateDraftText {
  return {
    title_ru: source.title_ru,
    title_kk: source.title_kk,
    preamble_ru: source.preamble_ru,
    preamble_kk: source.preamble_kk,
    body_template_ru: source.body_template_ru,
    body_template_kk: source.body_template_kk,
    basis_template_ru: source.basis_template_ru,
    basis_template_kk: source.basis_template_kk,
  };
}
export const getPersonnelOrderTemplateDraft = (type: string) => apiFetchJson<PersonnelOrderTemplateDraft | null>(`/admin/personnel-order-templates/${type}/draft`);
export const getPersonnelOrderTemplatePublished = (type: string) => apiFetchJson<PersonnelOrderTemplateDraft | null>(`/admin/personnel-order-templates/${type}/published`);
export const getPersonnelOrderTemplateEditorBase = (type: string) => apiFetchJson<PersonnelOrderTemplateEditorBase>(`/admin/personnel-order-templates/${type}/editor-base`);
export const createPersonnelOrderTemplateDraft = (type: string, body: PersonnelOrderTemplateDraftText & { base_source: "PUBLISHED" | "INITIAL"; base_published_template_version_id?: number; base_published_revision?: number }) => apiFetchJson<PersonnelOrderTemplateDraft>(`/admin/personnel-order-templates/${type}/draft`, { method: "POST", body: { ...editablePersonnelOrderTemplateDraftText(body), base_source: body.base_source, base_published_template_version_id: body.base_published_template_version_id, base_published_revision: body.base_published_revision } });
export const savePersonnelOrderTemplateDraft = (type: string, body: PersonnelOrderTemplateDraftText & { expected_revision: number }) => apiFetchJson<PersonnelOrderTemplateDraft>(`/admin/personnel-order-templates/${type}/draft`, { method: "PUT", body: { ...editablePersonnelOrderTemplateDraftText(body), expected_revision: body.expected_revision } });
export const publishPersonnelOrderTemplateDraft = (type: string, expected_revision: number) => apiFetchJson<PersonnelOrderTemplateDraft>(`/admin/personnel-order-templates/${type}/draft/publish`, { method: "POST", body: { expected_revision } });
export const previewPersonnelOrderTemplateDraft = (type: string, body: PersonnelOrderTemplateDraftText) => apiFetchJson<{ previews: Record<"ru" | "kk", PersonnelOrderTemplatePreview> }>(`/admin/personnel-order-templates/${type}/draft/preview`, { method: "POST", body: editablePersonnelOrderTemplateDraftText(body) });
