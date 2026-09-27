import { apiFetchJson } from "@/lib/api";

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
};

export function listPersonnelOrderTemplateCatalog() {
  return apiFetchJson<{ items: PersonnelOrderTemplateCatalogItem[] }>("/admin/personnel-order-templates");
}
