/** Section registry for PPR «Личная карточка» read-only page. */

export type PprCardSectionId =
  | "general"
  | "contacts"
  | "education"
  | "training"
  | "category"
  | "family"
  | "military"
  | "languages"
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
  { id: "contacts", title: "Контакты" },
  { id: "general", title: "Общие сведения" },
  { id: "education", title: "Образование" },
  { id: "training", title: "Обучение и повышение квалификации" },
  { id: "category", title: "Категория" },
  { id: "employment_biography", title: "Трудовая биография" },
  { id: "intended_employment", title: "Работа в текущей организации" },
  { id: "assignment", title: "Работа в текущей организации" },
  { id: "military", title: "Воинский учёт" },
  { id: "family", title: "Родственники" },
  { id: "languages", title: "Знание иностранных языков" },
  { id: "additional", title: "Примечание" },
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
