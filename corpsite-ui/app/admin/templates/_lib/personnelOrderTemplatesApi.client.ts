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
  required_fields: string[];
  notes: string;
  pilot_detail?: PersonnelOrderTemplatePilotDetail | null;
  template_detail?: PersonnelOrderTemplatePilotDetail | null;
};

export function listPersonnelOrderTemplateCatalog() {
  return apiFetchJson<{ items: PersonnelOrderTemplateCatalogItem[] }>("/admin/personnel-order-templates");
}
