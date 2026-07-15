import {
  buildPersonnelOrderPrintHref,
  type PersonnelOrderPrintLanguage,
} from "./personnelOrderPrintLanguage";

export const PERSONNEL_ORDER_PRINT_POPUP_BLOCKED_MESSAGE =
  "Браузер заблокировал всплывающее окно. Разрешите всплывающие окна для этого сайта и повторите.";

/** Open HTML print preview in a new tab; returns false when the browser blocks pop-ups. */
export function openPersonnelOrderPrintPreview(
  orderId: number,
  language: PersonnelOrderPrintLanguage,
  freshToken?: string | number | null,
): boolean {
  const popup = window.open(
    buildPersonnelOrderPrintHref(orderId, language, freshToken),
    "_blank",
    "noopener,noreferrer",
  );
  return popup != null;
}
