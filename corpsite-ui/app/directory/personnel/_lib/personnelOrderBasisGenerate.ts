import type { PersonnelOrderEditorialLocale, PersonnelOrderItemBasisFact } from "./personnelOrderEditorialTypes";

function cleanName(value: string | null | undefined): string {
  return String(value ?? "").trim();
}

/**
 * Generate basis wording from structured facts.
 * Does NOT claim correct morphology: uses optional genitive/possessive forms when provided,
 * otherwise nominative FIO with a safe template (HR must review / override).
 */
export function generatePersonnelOrderBasisText(
  fact: PersonnelOrderItemBasisFact,
  locale: PersonnelOrderEditorialLocale,
): string {
  const name = cleanName(fact.subjectEmployeeName);
  const genitiveRu = cleanName(fact.subjectEmployeeNameGenitiveRu) || name;
  const possessiveKk = cleanName(fact.subjectEmployeeNamePossessiveKk) || (name ? `${name}тың` : "");

  switch (fact.basisType) {
    case "PERSONAL_APPLICATION": {
      if (locale === "ru") {
        if (!genitiveRu) return "Основание: личное заявление.";
        return `Основание: личное заявление ${genitiveRu}.`;
      }
      if (!possessiveKk) return "Негіз: жеке өтініш.";
      return `Негіз: ${possessiveKk} жеке өтініші.`;
    }
    case "MEMO": {
      if (locale === "ru") {
        return name ? `Основание: служебная записка (${name}).` : "Основание: служебная записка.";
      }
      return name ? `Негіз: қызметтік жазба (${name}).` : "Негіз: қызметтік жазба.";
    }
    case "MANAGEMENT_SUBMISSION": {
      if (locale === "ru") {
        return name ? `Основание: представление (${name}).` : "Основание: представление.";
      }
      return name ? `Негіз: ұсыным (${name}).` : "Негіз: ұсыным.";
    }
    case "MEDICAL_CONCLUSION": {
      return locale === "ru" ? "Основание: медицинское заключение." : "Негіз: медициналық қорытынды.";
    }
    case "COMMISSION_PROTOCOL": {
      const num = cleanName(fact.documentNumber);
      const date = cleanName(fact.documentDate);
      const tail = [num && `№${num}`, date].filter(Boolean).join(" от ");
      if (locale === "ru") {
        return tail ? `Основание: протокол комиссии ${tail}.` : "Основание: протокол комиссии.";
      }
      return tail ? `Негіз: комиссия хаттамасы ${tail}.` : "Негіз: комиссия хаттамасы.";
    }
    case "COURT_ACT": {
      return locale === "ru" ? "Основание: судебный акт." : "Негіз: сот актісі.";
    }
    case "OTHER":
    default: {
      const free = cleanName(fact.freeText);
      if (free) return free;
      return locale === "ru" ? "Основание: —" : "Негіз: —";
    }
  }
}
