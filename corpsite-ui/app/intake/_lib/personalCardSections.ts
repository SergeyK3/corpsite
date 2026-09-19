export type PersonalCardSectionKey =
  | "general" | "education" | "training" | "qualification_category"
  | "employment_biography" | "current_organization" | "tenure_calculation"
  | "military" | "relatives" | "foreign_languages" | "note" | "additional";

export type PersonalCardSection = {
  key: PersonalCardSectionKey;
  title: string;
  uiOrder: number;
  pdfOrder: number | null;
  showInUi: boolean;
  showInPdf: boolean;
};

/** Single source of truth for HR personal-card section semantics and order. */
export const PERSONAL_CARD_SECTIONS: readonly PersonalCardSection[] = [
  { key: "general", title: "Общие сведения", uiOrder: 1, pdfOrder: 1, showInUi: true, showInPdf: true },
  { key: "education", title: "Образование", uiOrder: 2, pdfOrder: 2, showInUi: true, showInPdf: true },
  { key: "training", title: "Обучение и повышение квалификации", uiOrder: 3, pdfOrder: 3, showInUi: true, showInPdf: true },
  { key: "qualification_category", title: "Категория", uiOrder: 4, pdfOrder: 4, showInUi: true, showInPdf: true },
  { key: "employment_biography", title: "Трудовая биография", uiOrder: 5, pdfOrder: 5, showInUi: true, showInPdf: true },
  { key: "current_organization", title: "Работа в текущей организации", uiOrder: 6, pdfOrder: 6, showInUi: true, showInPdf: true },
  { key: "tenure_calculation", title: "Расчёт стажа", uiOrder: 7, pdfOrder: null, showInUi: true, showInPdf: false },
  { key: "military", title: "Воинский учёт", uiOrder: 8, pdfOrder: 7, showInUi: true, showInPdf: true },
  { key: "relatives", title: "Родственники", uiOrder: 9, pdfOrder: 8, showInUi: true, showInPdf: true },
  { key: "foreign_languages", title: "Знание иностранных языков", uiOrder: 10, pdfOrder: 9, showInUi: true, showInPdf: true },
  { key: "note", title: "Примечание", uiOrder: 11, pdfOrder: 10, showInUi: true, showInPdf: true },
  { key: "additional", title: "Иные дополнительные сведения", uiOrder: 12, pdfOrder: 11, showInUi: true, showInPdf: true },
] as const;

export function personalCardSectionTitle(key: PersonalCardSectionKey): string {
  return PERSONAL_CARD_SECTIONS.find((section) => section.key === key)?.title ?? key;
}

export const PERSONAL_CARD_UI_SECTIONS = PERSONAL_CARD_SECTIONS.filter((section) => section.showInUi)
  .slice().sort((left, right) => left.uiOrder - right.uiOrder);
export const PERSONAL_CARD_PDF_SECTIONS = PERSONAL_CARD_SECTIONS.filter((section) => section.showInPdf)
  .slice().sort((left, right) => (left.pdfOrder ?? Number.MAX_SAFE_INTEGER) - (right.pdfOrder ?? Number.MAX_SAFE_INTEGER));
