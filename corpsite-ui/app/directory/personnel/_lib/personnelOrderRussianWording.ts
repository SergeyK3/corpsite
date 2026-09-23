/**
 * Approved Russian forms used inside automatically generated order points.
 * These are deliberately separate from catalogue display names: a display name
 * such as "Приемное" needs its full personnel wording in a sentence.
 */
const RUSSIAN_ORDER_UNIT_FORMS: Record<string, string> = {
  "приемное": "приемное отделение",
};

function usable(value: string | null | undefined): value is string {
  const text = String(value || "").trim();
  return Boolean(text && text !== "—");
}

function lower(value: string): string {
  return value.trim().toLocaleLowerCase("ru-RU");
}

/**
 * Renders the Russian "position (unit)" construction. Unknown units are not
 * declined or invented; their normalized catalogue value remains visible for
 * later dictionary review.
 */
export function russianOrderAssignment(position: string | null | undefined, unit: string | null | undefined): string {
  const positionText = usable(position) ? lower(position) : "—";
  if (!usable(unit)) return positionText;
  const normalizedUnit = lower(unit);
  const orderUnit = RUSSIAN_ORDER_UNIT_FORMS[normalizedUnit] || normalizedUnit;
  return `${positionText} (${orderUnit})`;
}

/** Source FIO must remain untouched. Do not apply the new grammar to an unresolved person. */
export function russianEmployeeForOrder(name: string): string | null {
  return usable(name) ? name : null;
}

export const RUSSIAN_ORDER_UNIT_TEXT_DICTIONARY = RUSSIAN_ORDER_UNIT_FORMS;
