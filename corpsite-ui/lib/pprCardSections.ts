/** Section registry for PPR «Личная карточка» read-only page. */

export type PprCardSectionId =
  | "general"
  | "education"
  | "training"
  | "family"
  | "military"
  | "additional"
  | "employment_biography"
  | "intended_employment"
  | "assignment"
  | "orders"
  | "applications"
  | "onboarding"
  | "changes";

export type PprCardSectionDef = {
  id: PprCardSectionId;
  title: string;
};

export const PPR_CARD_SECTIONS: PprCardSectionDef[] = [
  { id: "general", title: "Общие сведения" },
  { id: "education", title: "Образование" },
  { id: "training", title: "Обучение и повышение квалификации" },
  { id: "family", title: "Родственники" },
  { id: "military", title: "Воинский учёт" },
  { id: "additional", title: "Дополнительные сведения" },
  { id: "employment_biography", title: "Трудовая биография" },
  { id: "intended_employment", title: "Предполагаемое трудоустройство" },
  { id: "assignment", title: "Трудовая деятельность" },
  { id: "orders", title: "Кадровые приказы" },
  { id: "applications", title: "Кадровые обращения" },
  { id: "onboarding", title: "Адаптация" },
  { id: "changes", title: "История изменений" },
];

export const PPR_CARD_DEFAULT_SECTION: PprCardSectionId = "general";

export function parsePprCardSection(value: string | null | undefined): PprCardSectionId {
  const normalized = String(value || "").trim().toLowerCase();
  const known = PPR_CARD_SECTIONS.find((s) => s.id === normalized);
  return known?.id ?? PPR_CARD_DEFAULT_SECTION;
}
