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
  required_variables?: Partial<Record<keyof PersonnelOrderTemplateDraftText, string[]>>;
  required_fields: string[];
  notes: string;
  pilot_detail?: PersonnelOrderTemplatePilotDetail | null;
  template_detail?: PersonnelOrderTemplatePilotDetail | null;
};

export function listPersonnelOrderTemplateCatalog() {
  return apiFetchJson<{ items: PersonnelOrderTemplateCatalogItem[] }>("/admin/personnel-order-templates");
}

export type PersonnelOrderTemplateDraft = { type_changed?: boolean;
  name_ru?: string | null; name_kk?: string | null;
  template_version_id: number; template_id?: number; item_type_code: string; version_number: number; status: string; revision: number; based_on_built_in: boolean;
  published_at?: string | null; published_by_user_id?: number | null;
  title_ru: string; title_kk: string; preamble_ru: string; preamble_kk: string; body_template_ru: string; body_template_kk: string; basis_template_ru: string; basis_template_kk: string;
};
export type PersonnelOrderTemplateDraftText = Pick<PersonnelOrderTemplateDraft, "title_ru" | "title_kk" | "preamble_ru" | "preamble_kk" | "body_template_ru" | "body_template_kk" | "basis_template_ru" | "basis_template_kk">;
export type PersonnelOrderTemplateEditorBase = PersonnelOrderTemplateDraftText & { source: "PUBLISHED" | "INITIAL"; template_id?: number | null; item_type_code: string; template_version_id: number | null; version_number: number | null; revision: number | null; };
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
export const getPersonnelOrderTemplateDraft = (type: string, templateId?: number) => apiFetchJson<PersonnelOrderTemplateDraft | null>(`/admin/personnel-order-templates/${type}/draft${templateQuery(templateId)}`);
export const getPersonnelOrderTemplatePublished = (type: string, templateId?: number) => apiFetchJson<PersonnelOrderTemplateDraft | null>(`/admin/personnel-order-templates/${type}/published${templateQuery(templateId)}`);
export const getPersonnelOrderTemplateEditorBase = (type: string, templateId?: number) => apiFetchJson<PersonnelOrderTemplateEditorBase>(`/admin/personnel-order-templates/${type}/editor-base${templateQuery(templateId)}`);
export const createPersonnelOrderTemplateDraft = (type: string, body: PersonnelOrderTemplateDraftText & { base_source: "PUBLISHED" | "INITIAL"; base_published_template_version_id?: number; base_published_revision?: number }, templateId?: number) => apiFetchJson<PersonnelOrderTemplateDraft>(`/admin/personnel-order-templates/${type}/draft${templateQuery(templateId)}`, { method: "POST", body: { ...editablePersonnelOrderTemplateDraftText(body), base_source: body.base_source, base_published_template_version_id: body.base_published_template_version_id, base_published_revision: body.base_published_revision } });
export const savePersonnelOrderTemplateDraft = (type: string, body: PersonnelOrderTemplateDraftText & { expected_revision: number; expected_template_version_id?: number }, templateId?: number) => apiFetchJson<PersonnelOrderTemplateDraft>(`/admin/personnel-order-templates/${type}/draft${templateQuery(templateId)}`, { method: "PUT", body: { ...editablePersonnelOrderTemplateDraftText(body), expected_revision: body.expected_revision, ...(body.expected_template_version_id == null ? {} : {expected_template_version_id: body.expected_template_version_id}) } });
export const publishPersonnelOrderTemplateDraft = (type: string, expected_revision: number, templateId?: number) => apiFetchJson<PersonnelOrderTemplateDraft>(`/admin/personnel-order-templates/${type}/draft/publish${templateQuery(templateId)}`, { method: "POST", body: { expected_revision } });
export const previewPersonnelOrderTemplateDraft = (type: string, body: PersonnelOrderTemplateDraftText) => apiFetchJson<{ previews: Record<"ru" | "kk", PersonnelOrderTemplatePreview> }>(`/admin/personnel-order-templates/${type}/draft/preview`, { method: "POST", body: editablePersonnelOrderTemplateDraftText(body) });

function templateQuery(templateId?: number) { return templateId == null ? "" : `?template_id=${templateId}`; }
export async function previewSavedPersonnelOrderTemplateDraft(draft: PersonnelOrderTemplateDraft) {
  const result = await apiFetchJson<{template_id: number; template_version_id: number; revision: number; previews: Record<"ru" | "kk", PersonnelOrderTemplatePreview>}>(`/admin/personnel-order-templates/${draft.item_type_code}/draft/preview?template_id=${draft.template_id}&expected_revision=${draft.revision}`);
  if (result.template_id !== draft.template_id || result.template_version_id !== draft.template_version_id || result.revision !== draft.revision) throw new Error("Версия предварительного просмотра не совпадает с открытым черновиком.");
  return result;
}
export type PersonnelIndependentTemplate = { template_id: number; item_type_code: string; name_ru: string; name_kk: string; is_default: boolean; template_version_id: number | null; draft_version_id: number | null; };
export const listPersonnelIndependentTemplates = (type: string) => apiFetchJson<{items: PersonnelIndependentTemplate[]}>(`/admin/personnel-order-templates/${type}/templates`);
export const listPersonnelTemplateVersions = (type: string, templateId: number) => apiFetchJson<{items: PersonnelOrderTemplateDraft[]}>(`/admin/personnel-order-templates/${type}/versions?template_id=${templateId}`);
export const copyPersonnelTemplate = (type: string, body: {source_type_code?: string; base_source?: "VERSION" | "INITIAL"; source_version_id?: number; expected_revision?: number; name_ru: string; name_kk: string}) => apiFetchJson<PersonnelOrderTemplateDraft>(`/admin/personnel-order-templates/${type}/copies`, {method: "POST", body});
export const removePersonnelTemplate = (template: PersonnelIndependentTemplate, archive = false) => apiFetchJson<{template_id: number; action: "DELETED" | "ARCHIVED"}>(`/admin/personnel-order-templates/${template.item_type_code}/templates/${template.template_id}${archive ? "/archive" : ""}`, {method: archive ? "POST" : "DELETE", body: {name_ru: template.name_ru, name_kk: template.name_kk}});
export const changePersonnelTemplateType = async (draft: PersonnelOrderTemplateDraft, targetType: string) => ({...await apiFetchJson<PersonnelOrderTemplateDraft>(`/admin/personnel-order-templates/${draft.item_type_code}/templates/${draft.template_id}/type`, {method: "POST", body: {target_type_code: targetType, expected_template_version_id: draft.template_version_id, expected_revision: draft.revision}}), type_changed: true});
