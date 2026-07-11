import type { PersonnelOrderPrintLanguage } from "./personnelOrderPrintLanguage";

export type LocalizedText = {
  kk?: string | null;
  ru?: string | null;
};

function cleanText(value: unknown): string | null {
  if (value == null) return null;
  if (typeof value === "object") return null;
  const text = String(value).trim();
  if (!text || text === "undefined" || text === "null" || text === "[object Object]") return null;
  return text;
}

export function localizedText(kk?: string | null, ru?: string | null): LocalizedText {
  return {
    ...(cleanText(kk) ? { kk: cleanText(kk) } : {}),
    ...(cleanText(ru) ? { ru: cleanText(ru) } : {}),
  };
}

export function localizedFromSingle(value: string | null | undefined): LocalizedText {
  const text = cleanText(value);
  return text ? { ru: text } : {};
}

/** Pick display lines for a language without inventing translations. */
export function resolveLocalizedLines(
  text: LocalizedText | null | undefined,
  language: PersonnelOrderPrintLanguage,
  fallback?: string | null,
): string[] {
  const kk = cleanText(text?.kk);
  const ru = cleanText(text?.ru);
  const fb = cleanText(fallback);

  if (language === "kk") {
    const value = kk || ru || fb;
    return value ? [value] : [];
  }
  if (language === "ru") {
    const value = ru || kk || fb;
    return value ? [value] : [];
  }

  if (kk && ru) {
    if (kk === ru) return [kk];
    return [kk, ru];
  }
  const value = kk || ru || fb;
  return value ? [value] : [];
}

export function resolveLocalizedText(
  text: LocalizedText | null | undefined,
  language: PersonnelOrderPrintLanguage,
  fallback?: string | null,
): string {
  const lines = resolveLocalizedLines(text, language, fallback);
  return lines[0] || cleanText(fallback) || "—";
}
