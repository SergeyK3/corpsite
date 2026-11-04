import type {ItemPayloadDraft} from "./personnelOrderPayload";

export const defaultHireBasis = (locale: "ru" | "kk"): string => locale === "kk" ? "жеке өтініші, еңбек шарты" : "личное заявление, трудовой договор";

export const hireRateNumber = (value: string): number => Number(value.trim().replace(",", "."));
export function hireTermsIssues(rate: string, hasBasis: boolean): string[] {
  const value = hireRateNumber(rate);
  return [
    ...(!rate.trim() ? ["Укажите ставку"] : !Number.isFinite(value) || value <= 0 || value > 2 ? ["Ставка должна быть больше 0 и не больше 2"] : []),
    ...(!hasBasis ? ["Заполните основание"] : []),
  ];
}
export function hasHireBasis(draft: ItemPayloadDraft): boolean {
  if(draft.hire_basis) return Boolean(draft.hire_basis.ru.trim()&&(draft.hire_basis.kk.trim()||draft.hire_basis.kk_intentionally_empty===true));
  if (draft.basis_entries?.length) return draft.basis_entries.some(entry => entry.document_type === "OTHER" ? Boolean(entry.other_text.trim()) : Boolean(entry.document_type && entry.basis_id));
  return Boolean(draft.basis_other_text?.trim() || draft.basis_ids?.length || draft.basis_id && draft.basis_id !== "OTHER");
}
