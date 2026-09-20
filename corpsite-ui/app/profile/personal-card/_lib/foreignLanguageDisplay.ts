const LEVEL_BY_LEGACY_VALUE: Record<string, string> = {
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

export const FOREIGN_LANGUAGE_LEVELS = [
  "Со словарём",
  "Читает и может объясняться",
  "Владеет свободно",
] as const;

/** Preserve an unknown historical value, but localize all known canonical and legacy forms. */
export function displayForeignLanguageLevel(value: string | null | undefined): string {
  const trimmed = value?.trim() ?? "";
  return LEVEL_BY_LEGACY_VALUE[trimmed] ?? trimmed;
}
