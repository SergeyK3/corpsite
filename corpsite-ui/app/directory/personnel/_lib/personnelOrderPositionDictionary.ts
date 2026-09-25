import type { PersonnelOrderPrintLanguage } from "./personnelOrderPrintLanguage";
import type { LocalizedText } from "./personnelOrderPrintLocalized";
import { resolveLocalizedText } from "./personnelOrderPrintLocalized";

function normalizeRussianPosition(value: string): string {
  return value
    .toLocaleLowerCase("ru-RU")
    .replace(/[‐‑–—]/g, "-")
    .trim()
    .replace(/\s+/g, " ")
    .replace(/\s*-\s*/g, "-");
}

const ruToKk: Record<string, string> = {
  "медсестра-анестезистка": "анестезист мейіргері",
};

/**
 * Applies only the approved exact pair. An explicitly persisted Kazakh value
 * always wins, so this display fallback cannot overwrite editorial text.
 */
export function resolvePersonnelOrderPositionText(
  value: LocalizedText | null | undefined,
  language: PersonnelOrderPrintLanguage,
): string {
  if (language !== "kk") return resolveLocalizedText(value, language);
  const savedKk = String(value?.kk || "").trim();
  if (savedKk) return savedKk;
  const russian = String(value?.ru || "").trim();
  return ruToKk[normalizeRussianPosition(russian)] || resolveLocalizedText(value, language);
}
