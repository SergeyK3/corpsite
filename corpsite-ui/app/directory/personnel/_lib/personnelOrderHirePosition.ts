export type HirePositionManualForms = {ru: boolean; kk: boolean};
type Wording = {hire_position_manual_forms?: HirePositionManualForms; position_document_nominative_ru?: string; position_document_possessive_kk?: string;
  document_position?: {name: string; name_kk?: string | null}};
export function hirePositionManualForms(value: Wording, reference?: {name: string; name_kk?: string | null; document_nominative_ru?: string | null; document_possessive_kk?: string | null}): HirePositionManualForms {
  if (value.hire_position_manual_forms) return {...value.hire_position_manual_forms};
  const ru=value.position_document_nominative_ru || "", kk=value.position_document_possessive_kk || "";
  return {ru: Boolean(ru && ru !== (reference?.document_nominative_ru || reference?.name || value.document_position?.name)),
    kk: Boolean(kk && kk !== (reference?.document_possessive_kk || reference?.name_kk || value.document_position?.name_kk))};
}
