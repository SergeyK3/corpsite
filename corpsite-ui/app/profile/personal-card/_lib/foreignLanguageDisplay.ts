export const FOREIGN_LANGUAGE_LEVELS = [
  "Со словарём",
  "Читает и может объясняться",
  "Владеет свободно",
] as const;

export type ForeignLanguageLevel = (typeof FOREIGN_LANGUAGE_LEVELS)[number];

const LEVEL_BY_LEGACY_VALUE: Record<string, ForeignLanguageLevel> = {
  dictionary: "Со словарём",
  conversational: "Читает и может объясняться",
  fluent: "Владеет свободно",
  A1: "Со словарём",
  A2: "Со словарём",
  B1: "Читает и может объясняться",
  B2: "Читает и может объясняться",
  C1: "Владеет свободно",
  C2: "Владеет свободно",
};

function isForeignLanguageLevel(value: string): value is ForeignLanguageLevel {
  return FOREIGN_LANGUAGE_LEVELS.some((level) => level === value);
}

/** Preserve an unknown historical value, but localize all known canonical and legacy forms. */
export function displayForeignLanguageLevel(value: string | null | undefined): string {
  const trimmed = value?.trim() ?? "";
  return LEVEL_BY_LEGACY_VALUE[trimmed] ?? trimmed;
}

/** Converts a stored legacy/canonical value into one of the editor's selectable levels. */
export function foreignLanguageLevelForEditor(value: string | null | undefined): ForeignLanguageLevel {
  const displayed = displayForeignLanguageLevel(value);
  return isForeignLanguageLevel(displayed) ? displayed : FOREIGN_LANGUAGE_LEVELS[0];
}
