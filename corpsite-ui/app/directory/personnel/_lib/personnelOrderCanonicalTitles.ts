/** Read-only projection of the personnel-order template specification.
 * Keep this in sync by importing the generated catalog rather than placing
 * titles in a dialog; PUBLISHED content may override these values.
 */
export const PERSONNEL_ORDER_CANONICAL_TITLES: Record<string, { ru: string; kk: string }> = {
  HIRE: { ru: "О приёме на работу", kk: "Жұмысқа қабылдау туралы" },
  TRANSFER: { ru: "О переводе", kk: "Ауыстыру туралы" },
  TERMINATION: { ru: "Об увольнении", kk: "Еңбек шартын бұзу туралы" },
  CONCURRENT_DUTY_START: { ru: "Об установлении совмещения", kk: "Қоса атқару туралы" },
  CONCURRENT_DUTY_END: { ru: "О прекращении совмещения", kk: "Ставканы алып тастау туралы" },
  "LEAVE.ANNUAL.GRANT": { ru: "О трудовом отпуске", kk: "Еңбек демалысы туралы" },
  "LEAVE.UNPAID.GRANT": { ru: "Об отпуске без содержания", kk: "Жалақы сақталмайтын демалыс беру туралы" },
  "LEAVE.CHILDCARE.GRANT": { ru: "О неоплачиваемом отпуске по уходу за ребенком", kk: "Бала күтіміне байланысты жалақы сақталмайтын демалыс туралы" },
  "LEAVE.ANNUAL.RECALL": { ru: "Об отзыве из отпуска", kk: "Еңбек демалысынан шақырту туралы" },
  SUPPLEMENTARY_PAY: { ru: "О дополнительной оплате", kk: "Қосымша ақы туралы" },
  RETURN_FROM_CHILDCARE_LEAVE: { ru: "О выходе на работу из отпуска по уходу за ребёнком", kk: "Бала күтіміне байланысты демалыстан жұмысқа шығу туралы" },
};

export function personnelOrderCanonicalTitle(type: string, locale: "ru" | "kk"): string {
  return PERSONNEL_ORDER_CANONICAL_TITLES[type]?.[locale] || "";
}
