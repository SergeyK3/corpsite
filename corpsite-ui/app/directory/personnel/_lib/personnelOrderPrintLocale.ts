import type { PersonnelOrderPrintLanguage } from "./personnelOrderPrintLanguage";

export type PersonnelOrderPrintDictionary = {
  documentType: string;
  orderVerb: string;
  basis: string;
  familiarization: string;
  familiarizationDate: string;
  signatureCaption: string;
  /** Human-facing print watermark for DRAFT. */
  draft: string;
  /** Human-facing print watermark for READY_FOR_SIGNATURE. */
  readyForSignature: string;
  cancelled: string;
  missingTranslation: string;
  orderNumber: string;
  orderDate: string;
  placeOfIssue: string;
  itemsEmpty: string;
  rateUnit: string;
};

export const PERSONNEL_ORDER_PRINT_DICTIONARIES: Record<"kk" | "ru", PersonnelOrderPrintDictionary> = {
  kk: {
    documentType: "БҰЙРЫҚ",
    orderVerb: "БҰЙЫРАМЫН:",
    basis: "Негіздеме",
    familiarization: "Бұйрықпен таныстым:",
    familiarizationDate: "«___» __________ 20__ ж.",
    signatureCaption: "қолы",
    draft: "ЖОБА",
    readyForSignature: "ҚОЛ ҚОЮҒА",
    cancelled: "КҮШІ ЖОЙЫЛҒАН",
    missingTranslation: "Мәтін дайындалмаған",
    orderNumber: "№",
    orderDate: "Күні",
    placeOfIssue: "Астана қ.",
    itemsEmpty: "Тармақтар жоқ.",
    rateUnit: "мөлшерлеме",
  },
  ru: {
    documentType: "ПРИКАЗ",
    orderVerb: "ПРИКАЗЫВАЮ:",
    basis: "Основание",
    familiarization: "С приказом ознакомлен(а):",
    familiarizationDate: "«___» __________ 20__ г.",
    signatureCaption: "подпись",
    draft: "ПРОЕКТ",
    readyForSignature: "НА ПОДПИСЬ",
    cancelled: "АННУЛИРОВАН",
    missingTranslation: "Текст не подготовлен",
    orderNumber: "№",
    orderDate: "Дата",
    placeOfIssue: "г. Астана",
    itemsEmpty: "Пункты отсутствуют.",
    rateUnit: "ставки",
  },
};

export function printDictionariesForLanguage(
  language: PersonnelOrderPrintLanguage,
): PersonnelOrderPrintDictionary[] {
  if (language === "kk") return [PERSONNEL_ORDER_PRINT_DICTIONARIES.kk];
  if (language === "ru") return [PERSONNEL_ORDER_PRINT_DICTIONARIES.ru];
  return [PERSONNEL_ORDER_PRINT_DICTIONARIES.kk, PERSONNEL_ORDER_PRINT_DICTIONARIES.ru];
}

export function primaryPrintDictionary(
  language: PersonnelOrderPrintLanguage,
): PersonnelOrderPrintDictionary {
  return language === "kk"
    ? PERSONNEL_ORDER_PRINT_DICTIONARIES.kk
    : PERSONNEL_ORDER_PRINT_DICTIONARIES.ru;
}

function bilingualSlash(kk: string, ru: string): string[] {
  if (kk === ru) return [kk];
  return [`${kk} / ${ru}`];
}

/**
 * Human-facing watermark lines for print.
 * System codes (DRAFT / READY_FOR_SIGNATURE / …) are never shown as-is.
 */
export function statusMarkLinesForLanguage(
  statusMark: "draft" | "unsigned" | "cancelled",
  language: PersonnelOrderPrintLanguage,
): string[] {
  const dictionaries = printDictionariesForLanguage(language);
  if (statusMark === "cancelled") {
    if (language === "kk-ru") {
      return bilingualSlash(
        PERSONNEL_ORDER_PRINT_DICTIONARIES.kk.cancelled,
        PERSONNEL_ORDER_PRINT_DICTIONARIES.ru.cancelled,
      );
    }
    return dictionaries.map((dict) => dict.cancelled);
  }
  if (statusMark === "draft") {
    if (language === "kk-ru") {
      return bilingualSlash(
        PERSONNEL_ORDER_PRINT_DICTIONARIES.kk.draft,
        PERSONNEL_ORDER_PRINT_DICTIONARIES.ru.draft,
      );
    }
    return dictionaries.map((dict) => dict.draft);
  }
  // unsigned → READY_FOR_SIGNATURE → «НА ПОДПИСЬ» / «ҚОЛ ҚОЮҒА»
  if (language === "kk-ru") {
    return bilingualSlash(
      PERSONNEL_ORDER_PRINT_DICTIONARIES.kk.readyForSignature,
      PERSONNEL_ORDER_PRINT_DICTIONARIES.ru.readyForSignature,
    );
  }
  return dictionaries.map((dict) => dict.readyForSignature);
}
