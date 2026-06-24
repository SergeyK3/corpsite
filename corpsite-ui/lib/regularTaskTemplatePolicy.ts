export type RegularTaskTemplateLike = {
  is_active?: boolean;
};

export function isTemplateArchived(template: RegularTaskTemplateLike): boolean {
  return template.is_active === false;
}

export function canEditTemplate(template: RegularTaskTemplateLike): boolean {
  return !isTemplateArchived(template);
}

export const TEMPLATE_TABLE_ACTIONS = ["open", "copy", "edit", "archive"] as const;

export type TemplateTableAction = (typeof TEMPLATE_TABLE_ACTIONS)[number];

export function listStatusFilterToApi(status: "all" | "active" | "archived"): "all" | "active" | "inactive" {
  if (status === "archived") return "inactive";
  return status;
}
