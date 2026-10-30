import type { PersonnelOrderPrintLanguage } from "./personnelOrderPrintLanguage";
import type { LocalizedText } from "./personnelOrderPrintLocalized";
import type { PersonnelOrderPrintViewModel } from "./personnelOrderPrintViewModel";

export class EducationPrintError extends Error {
  constructor(public readonly code: string, message: string) { super(message); }
}

/** Education documents never fall back to the other language, even partially. */
export function educationPrintModel(model: PersonnelOrderPrintViewModel, language: PersonnelOrderPrintLanguage): PersonnelOrderPrintViewModel {
  if (model.documentTypeCode !== "EDUCATION_INFORMATION_CHANGE") return model;
  if (language === "kk-ru") throw new EducationPrintError("EDUCATION_SINGLE_LANGUAGE_REQUIRED", "Для приказа об образовании сформируйте отдельные документы RU и KK. Выберите один язык.");
  const only = (text: LocalizedText | null | undefined): LocalizedText => ({ [language]: text?.[language] || null });
  for (const [label, value] of [["заголовок", model.title], ["преамбула", model.preamble],
    ...model.items.flatMap(item => [["распорядительный текст", item.body], ["основание", item.basis]])] as Array<[string, LocalizedText | null]>) {
    if (!value?.[language]?.trim()) throw new EducationPrintError("EDUCATION_PRINT_TEXT_MISSING", `Не заполнен ${label} ${language.toUpperCase()}. Текст другого языка не подставляется.`);
  }
  return { ...model, organization: only(model.organization), title: only(model.title), preamble: only(model.preamble),
    placeOfIssue: only(model.placeOfIssue), closing: model.closing ? only(model.closing) : null,
    signatory: model.signatory ? { ...model.signatory, position: model.signatory.position ? only(model.signatory.position) : null } : model.signatory,
    items: model.items.map(item => ({ ...item, body: only(item.body), basis: only(item.basis) })),
    basis: model.basis.map(only).filter(text => Boolean(text[language]?.trim())) };
}
