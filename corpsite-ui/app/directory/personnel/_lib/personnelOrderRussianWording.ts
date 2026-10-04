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

function text(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

/** The existing document_forms_ru contract wins over any calculated suggestion. */
export function savedRussianEmployeeNameForm(employee: unknown, form: "dative" | "genitive"): string {
  if (!employee || typeof employee !== "object") return "";
  const row = employee as Record<string, unknown>;
  const key = `employee_full_name_${form}_ru`;
  const forms = row.document_forms_ru;
  const name = row.name;
  return text(forms && typeof forms === "object" ? (forms as Record<string, unknown>)[key] : null)
    || text(row[key])
    || text(name && typeof name === "object" ? (name as Record<string, unknown>)[`full_name_${form}_ru`] : null);
}

/**
 * A conservative RU genitive suggestion, not a confirmed reference form.
 * Use structured names or the existing employee FIO order (surname/name/patronymic).
 * Unresolved gender, initials and ambiguous surname patterns require manual input.
 * Never change employee/reference data or derive this case from the RU dative.
 */
export function russianEmployeeGenitiveForOrder(employee: unknown): string {
  const saved = savedRussianEmployeeNameForm(employee, "genitive");
  if (saved) return saved;
  if (!employee || typeof employee !== "object") return "";
  const row = employee as Record<string, unknown>;
  const fallback = text(row.fio ?? row.full_name).split(/\s+/);
  const structured = Boolean(text(row.last_name) && text(row.first_name));
  if (!structured && fallback.length !== 3) return "";
  const [last, first, middle] = structured
    ? [text(row.last_name), text(row.first_name), text(row.middle_name)] : fallback;
  if (![last, first, middle].every(part => /^[А-ЯЁа-яё]{2,}$/u.test(part))) return "";
  const female = /(?:овна|евна|ична)$/iu.test(middle);
  const male = /ич$/iu.test(middle);
  if (!female && !male) return "";
  const consonant = /[бвгджзклмнпрстфхцчшщ]$/iu;
  const aGenitive = (part: string) => part.slice(0, -1) + (/[гкхжчшщ]а$/iu.test(part) ? "и" : "ы");
  let family = "";
  if (female && /(?:ова|ева|ина|ына)$/iu.test(last)) family = last.slice(0, -1) + "ой";
  else if (female && /ая$/iu.test(last)) family = last.slice(0, -2) + "ой";
  else if (female && /яя$/iu.test(last)) family = last.slice(0, -2) + "ей";
  else if (male && /(?:ский|цкий|ый|ой)$/iu.test(last)) family = last.slice(0, -2) + "ого";
  else if (/[оеёиуыю]$/iu.test(last) || /(?:их|ых)$/iu.test(last)) family = last;
  else if (female && /[бвгджзклмнпрстфхцчшщйь]$/iu.test(last)) family = last;
  else if (male && consonant.test(last)) family = last + "а";
  else if (male && /[йь]$/iu.test(last)) family = last.slice(0, -1) + "я";
  if (!family) return "";
  // Common irregular first names cannot be handled by a final-letter rule.
  const irregular: Record<string, string> = { "Павел": "Павла", "Лев": "Льва", "Пётр": "Петра", "Петр": "Петра", "Любовь": "Любови" };
  let given = irregular[first] || "";
  if (!given && /а$/iu.test(first)) given = aGenitive(first);
  else if (!given && /я$/iu.test(first)) given = first.slice(0, -1) + "и";
  else if (!given && female && /[бвгджзклмнпрстфхцчшщйь]$/iu.test(first)) given = first;
  else if (!given && male && /[йь]$/iu.test(first)) given = first.slice(0, -1) + "я";
  else if (!given && male && consonant.test(first)) given = first + "а";
  else if (!given && /[оеёиуыю]$/iu.test(first)) given = first;
  if (!given) return "";
  return [family, given, female ? aGenitive(middle) : middle + "а"].join(" ");
}
