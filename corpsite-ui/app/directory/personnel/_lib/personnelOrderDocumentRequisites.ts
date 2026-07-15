/**
 * Structured document requisites (order date, signatory) — separate from editorial closing text.
 * Values come from Personnel Order header fields (frozen snapshots on the order record).
 */

import type { PersonnelOrderEditorialUiLocale } from "./personnelOrderEditorialUi";
import { formatPersonnelOrderPrintDate } from "./personnelOrderPrintFormat";
import type { PersonnelOrderHeader } from "./personnelOrdersApi.client";

export type PersonnelOrderRequisitesSnapshot = Pick<
  PersonnelOrderHeader,
  "order_date" | "signed_by_name" | "signed_by_position"
>;

export type PersonnelOrderSignatoryDisplay = {
  position: string | null;
  fio: string | null;
};

export type PersonnelOrderDocumentRequisitesDisplay = {
  orderDate: string | null;
  formattedDate: string | null;
  signatory: PersonnelOrderSignatoryDisplay;
};

function optionalTrim(value: string | null | undefined): string | null {
  if (value == null) return null;
  const text = String(value).trim();
  return text || null;
}

/** Resolve signatory from frozen order header snapshots (not live employee directory). */
export function resolvePersonnelOrderSignatoryDisplay(
  order: Pick<PersonnelOrderHeader, "signed_by_name" | "signed_by_position">,
): PersonnelOrderSignatoryDisplay {
  return {
    position: optionalTrim(order.signed_by_position),
    fio: optionalTrim(order.signed_by_name),
  };
}

export function hasPersonnelOrderRequisitesDate(orderDate: string | null | undefined): boolean {
  return Boolean(optionalTrim(orderDate));
}

export function hasPersonnelOrderSignatory(
  signatory: PersonnelOrderSignatoryDisplay,
): boolean {
  return Boolean(signatory.position || signatory.fio);
}

/** Prefer live header-editor draft over last saved order snapshot for in-drawer preview. */
export function mergePersonnelOrderRequisitesForPreview(
  saved: PersonnelOrderRequisitesSnapshot,
  draft: PersonnelOrderRequisitesSnapshot | null | undefined,
): PersonnelOrderRequisitesSnapshot {
  return draft ?? saved;
}

export function buildPersonnelOrderDocumentRequisitesDisplay(
  order: PersonnelOrderRequisitesSnapshot,
  locale: PersonnelOrderEditorialUiLocale,
): PersonnelOrderDocumentRequisitesDisplay {
  const orderDate = optionalTrim(order.order_date);
  const signatory = resolvePersonnelOrderSignatoryDisplay(order);
  const formattedDate = orderDate ? formatPersonnelOrderPrintDate(orderDate, locale) : null;
  return { orderDate, formattedDate, signatory };
}
