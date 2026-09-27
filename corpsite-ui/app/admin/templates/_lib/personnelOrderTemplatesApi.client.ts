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
  title_ru: string; title_kk: string; preamble_ru: string; preamble_kk: string; body_template_ru: string; body_template_kk: string; basis_template_ru: string; basis_template_kk: string;
};
export type PersonnelOrderTemplateDraftText = Pick<PersonnelOrderTemplateDraft, "title_ru" | "title_kk" | "preamble_ru" | "preamble_kk" | "body_template_ru" | "body_template_kk" | "basis_template_ru" | "basis_template_kk">;
export const getPersonnelOrderTemplateDraft = (type: string) => apiFetchJson<PersonnelOrderTemplateDraft | null>(`/admin/personnel-order-templates/${type}/draft`);
export const createPersonnelOrderTemplateDraft = (type: string) => apiFetchJson<PersonnelOrderTemplateDraft>(`/admin/personnel-order-templates/${type}/draft`, { method: "POST" });
export const savePersonnelOrderTemplateDraft = (type: string, body: PersonnelOrderTemplateDraftText & { expected_revision: number }) => apiFetchJson<PersonnelOrderTemplateDraft>(`/admin/personnel-order-templates/${type}/draft`, { method: "PUT", body });
export const previewPersonnelOrderTemplateDraft = (type: string, body: PersonnelOrderTemplateDraftText) => apiFetchJson<{ previews: Record<"ru" | "kk", PersonnelOrderTemplatePreview> }>(`/admin/personnel-order-templates/${type}/draft/preview`, { method: "POST", body });
