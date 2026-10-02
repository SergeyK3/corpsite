/** Canonical document wording, resolved from directory identity rather than UI ids. */
const ORG_UNIT_DOCUMENT_GENITIVE_KK: Record<number, string> = {
  59: "Сәулелік диагностика бөлімшесінің",
};

type PositionReference = {
  id?: number | null;
  name?: string | null;
  code?: string | null;
} | null | undefined;

const POSITION_DOCUMENT_FORMS_BY_CANONICAL_KEY: Record<string, {
  position_document_possessive_kk: string;
  position_document_nominative_ru: string;
}> = {
  "врач": {
    position_document_possessive_kk: "дәрігері",
    position_document_nominative_ru: "врач",
  },
};

function canonicalPositionKey(position: PositionReference): string {
  const raw = position?.code || position?.name || "";
  return raw.trim().toLocaleLowerCase("ru-RU").replace(/\s+/g, " ");
}

export function resolvePersonnelOrderDocumentForms(orgUnitId: number | null | undefined, position: PositionReference) {
  const positionForms = POSITION_DOCUMENT_FORMS_BY_CANONICAL_KEY[canonicalPositionKey(position)];
  return {
    org_unit_document_genitive_kk: orgUnitId == null ? "" : ORG_UNIT_DOCUMENT_GENITIVE_KK[orgUnitId] || "",
    position_document_possessive_kk: positionForms?.position_document_possessive_kk || "",
    position_document_nominative_ru: positionForms?.position_document_nominative_ru || "",
  };
}
