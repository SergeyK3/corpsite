export const TEMPLATE_SECTIONS = {
  tasks: "tasks",
  personnelOrders: "personnel-orders",
} as const;

export type TemplateSection = (typeof TEMPLATE_SECTIONS)[keyof typeof TEMPLATE_SECTIONS];

type SearchParamsRecord = Record<string, string | string[] | undefined>;

export function resolveTemplateSection(value: string | null | undefined): TemplateSection {
  return value === TEMPLATE_SECTIONS.personnelOrders
    ? TEMPLATE_SECTIONS.personnelOrders
    : TEMPLATE_SECTIONS.tasks;
}

export function buildTemplateSectionHref(section: TemplateSection, currentSearch: URLSearchParams): string {
  const params = new URLSearchParams(currentSearch.toString());
  params.set("section", section);
  return `/admin/templates?${params.toString()}`;
}

export function buildLegacyRegularTaskTemplatesHref(searchParams: SearchParamsRecord): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(searchParams)) {
    if (key === "section") continue;
    if (Array.isArray(value)) {
      for (const item of value) params.append(key, item);
    } else if (typeof value === "string") {
      params.set(key, value);
    }
  }
  params.set("section", TEMPLATE_SECTIONS.tasks);
  return `/admin/templates?${params.toString()}`;
}
