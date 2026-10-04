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

export function resolvePersonnelOrderDocumentForms(position: PositionReference) {
  const positionForms = POSITION_DOCUMENT_FORMS_BY_CANONICAL_KEY[canonicalPositionKey(position)];
  return {
    position_document_possessive_kk: positionForms?.position_document_possessive_kk || "",
    position_document_nominative_ru: positionForms?.position_document_nominative_ru || "",
  };
}
