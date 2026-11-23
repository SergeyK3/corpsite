export const PERSONNEL_ORDER_TERMINATION_REASONS = [
  { code: "EMPLOYEE_INITIATIVE", ru: "по инициативе работника", kk: "жұмыскердің бастамасы бойынша" },
  { code: "EMPLOYER_INITIATIVE", ru: "по инициативе работодателя", kk: "жұмыс берушінің бастамасы бойынша" },
  { code: "CONTRACT_EXPIRATION", ru: "В связи с истечением срока трудового договора", kk: "Еңбек шарты мерзімінің аяқталуына байланысты" },
] as const;

export function personnelOrderTerminationReasonText(value: string | null | undefined, locale: "ru" | "kk"): string {
  const raw = String(value || "").trim();
  return PERSONNEL_ORDER_TERMINATION_REASONS.find(reason => reason.code === raw)?.[locale] || raw;
}
