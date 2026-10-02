export type PersonnelOrderBasisLanguage = "kk" | "ru";

/**
 * Editorial snapshots store historic BASIS strings verbatim.  The document
 * and print renderers own the visible label and terminal punctuation, so a
 * stored label or full stop must not be rendered a second time.
 */
export function normalizePersonnelOrderBasisText(
  value: string | null | undefined,
  language: PersonnelOrderBasisLanguage,
): string {
  const label = language === "kk" ? "Негіз" : "Основание";
  return String(value || "")
    .trim()
    .replace(new RegExp(`^(?:${label}\\s*:\\s*)+`, "i"), "")
    .replace(/[.]+$/u, "")
    .trim();
}
