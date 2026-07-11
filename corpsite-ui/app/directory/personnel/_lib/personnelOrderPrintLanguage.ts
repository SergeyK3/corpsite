export const PERSONNEL_ORDER_PRINT_LANGUAGES = ["kk", "ru", "kk-ru"] as const;

export type PersonnelOrderPrintLanguage = (typeof PERSONNEL_ORDER_PRINT_LANGUAGES)[number];

export const PERSONNEL_ORDER_PRINT_LANGUAGE_DEFAULT: PersonnelOrderPrintLanguage = "ru";

export const PERSONNEL_ORDER_PRINT_LANGUAGE_LABELS: Record<PersonnelOrderPrintLanguage, string> = {
  kk: "Қазақша",
  ru: "Русский",
  "kk-ru": "Қазақша / Русский",
};

export function isPersonnelOrderPrintLanguage(value: unknown): value is PersonnelOrderPrintLanguage {
  return (
    typeof value === "string" &&
    (PERSONNEL_ORDER_PRINT_LANGUAGES as readonly string[]).includes(value)
  );
}

/** Parse query language. Missing → default ru. Unknown → null (caller shows error or falls back). */
export function parsePersonnelOrderPrintLanguage(
  value: string | null | undefined,
  options?: { fallbackToDefault?: boolean },
): PersonnelOrderPrintLanguage | null {
  const raw = String(value ?? "").trim().toLowerCase();
  if (!raw) {
    return options?.fallbackToDefault === false ? null : PERSONNEL_ORDER_PRINT_LANGUAGE_DEFAULT;
  }
  if (isPersonnelOrderPrintLanguage(raw)) return raw;
  return options?.fallbackToDefault ? PERSONNEL_ORDER_PRINT_LANGUAGE_DEFAULT : null;
}

export function buildPersonnelOrderPrintHref(
  orderId: number,
  language: PersonnelOrderPrintLanguage = PERSONNEL_ORDER_PRINT_LANGUAGE_DEFAULT,
): string {
  return `/directory/personnel/orders/${orderId}/print?language=${language}`;
}

export function isPersonnelOrderPrintRoute(pathname: string | null | undefined): boolean {
  return /\/directory\/personnel\/orders\/\d+\/print(?:\/|$)/.test(String(pathname || ""));
}

export function isPersonnelOrderPdfRoute(pathname: string | null | undefined): boolean {
  return /\/directory\/personnel\/orders\/\d+\/pdf(?:\/|$)/.test(String(pathname || ""));
}
