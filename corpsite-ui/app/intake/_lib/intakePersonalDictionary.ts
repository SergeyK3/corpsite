/**
 * Intake personal-field dictionaries.
 *
 * Canonical citizenship labels align with WP-CL-010 normalization text
 * (`app/control_list_import/other_ppr_normalization/fields.py`: «Казахстан», «Россия»).
 * Legacy fixture values (e.g. «Республика Казахстан», «казах») remain valid when already saved.
 */

export const INTAKE_DICTIONARY_RESULT_LIMIT = 15;

/** Most likely citizenship values when the search box is empty. */
export const INTAKE_CITIZENSHIP_POPULAR: readonly string[] = [
  "Казахстан",
  "Россия",
  "Кыргызстан",
  "Узбекистан",
  "Таджикистан",
  "Беларусь",
  "Украина",
  "Азербайджан",
  "Армения",
  "Грузия",
  "Туркменистан",
  "Китай",
  "Монголия",
  "Турция",
  "Другое",
];

const INTAKE_CITIZENSHIP_EXTENDED: readonly string[] = [
  "Республика Казахстан",
  "Австралия",
  "Австрия",
  "Афганистан",
  "Великобритания",
  "Венгрия",
  "Германия",
  "Египет",
  "Израиль",
  "Индия",
  "Иран",
  "Испания",
  "Италия",
  "Канада",
  "Латвия",
  "Литва",
  "Молдова",
  "ОАЭ",
  "Польша",
  "Сирия",
  "США",
  "Франция",
  "Эстония",
  "Япония",
  "Южная Корея",
];

/** Full citizenship catalog for search (popular order preserved separately). */
export const INTAKE_CITIZENSHIP_CATALOG: readonly string[] = dedupeCatalog([
  ...INTAKE_CITIZENSHIP_POPULAR,
  ...INTAKE_CITIZENSHIP_EXTENDED,
]);

/** Most likely nationality values when the search box is empty (plural, lowercase). */
export const INTAKE_NATIONALITY_POPULAR: readonly string[] = [
  "казахи",
  "русские",
  "узбеки",
  "украинцы",
  "уйгуры",
  "татары",
  "немцы",
  "корейцы",
  "кыргызы",
  "азербайджанцы",
  "белорусы",
  "таджики",
  "армяне",
  "чеченцы",
  "другое",
];

/** Legacy singular / alternate forms kept for already-saved drafts (not shown in popular list). */
const INTAKE_NATIONALITY_LEGACY: readonly string[] = ["казах"];

const INTAKE_NATIONALITY_EXTENDED: readonly string[] = [
  "алтайцы",
  "башкиры",
  "дунгане",
  "евреи",
  "калмыки",
  "лезгины",
  "молдаване",
  "поляки",
  "турки",
  "чуваши",
  ...INTAKE_NATIONALITY_LEGACY,
];

/** Full nationality catalog for search. */
export const INTAKE_NATIONALITY_CATALOG: readonly string[] = dedupeCatalog([
  ...INTAKE_NATIONALITY_POPULAR,
  ...INTAKE_NATIONALITY_EXTENDED,
]);

function dedupeCatalog(values: readonly string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const value of values) {
    const trimmed = value.trim();
    if (!trimmed) continue;
    const key = trimmed.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(trimmed);
  }
  return out;
}

export function normalizeIntakeDictionaryQuery(query: string): string {
  return query.trim().toLowerCase();
}

export function intakeDictionaryWords(value: string): string[] {
  return value
    .trim()
    .toLowerCase()
    .split(/[\s-]+/)
    .filter(Boolean);
}

export function matchesIntakeDictionaryOption(option: string, query: string): boolean {
  const normalizedQuery = normalizeIntakeDictionaryQuery(query);
  if (!normalizedQuery) return true;
  const lowerOption = option.toLowerCase();
  if (lowerOption.includes(normalizedQuery)) return true;
  return intakeDictionaryWords(option).some((word) => word.startsWith(normalizedQuery));
}

export function rankIntakeDictionaryMatch(option: string, query: string): number {
  const normalizedQuery = normalizeIntakeDictionaryQuery(query);
  if (!normalizedQuery) return 0;
  const words = intakeDictionaryWords(option);
  if (words.some((word) => word.startsWith(normalizedQuery))) return 0;
  const lowerOption = option.toLowerCase();
  if (lowerOption.startsWith(normalizedQuery)) return 1;
  if (lowerOption.includes(normalizedQuery)) return 2;
  return 3;
}

export function filterIntakeDictionaryOptions(
  catalog: readonly string[],
  popular: readonly string[],
  query: string,
  limit = INTAKE_DICTIONARY_RESULT_LIMIT,
): string[] {
  const normalizedQuery = normalizeIntakeDictionaryQuery(query);
  if (!normalizedQuery) {
    const popularSet = new Set(catalog.map((entry) => entry.toLowerCase()));
    return popular.filter((entry) => popularSet.has(entry.toLowerCase())).slice(0, limit);
  }

  const matched = catalog.filter((entry) => matchesIntakeDictionaryOption(entry, normalizedQuery));
  matched.sort((left, right) => {
    const rankDiff =
      rankIntakeDictionaryMatch(left, normalizedQuery) - rankIntakeDictionaryMatch(right, normalizedQuery);
    if (rankDiff !== 0) return rankDiff;
    return left.localeCompare(right, "ru");
  });
  return matched.slice(0, limit);
}

export function isIntakeDictionaryValue(value: string, catalog: readonly string[]): boolean {
  const normalized = normalizeIntakeDictionaryQuery(value);
  if (!normalized) return true;
  return catalog.some((entry) => entry.toLowerCase() === normalized);
}

export function resolveIntakeDictionarySelection(
  input: string,
  catalog: readonly string[],
): string | null {
  const normalized = normalizeIntakeDictionaryQuery(input);
  if (!normalized) return null;
  const exact = catalog.find((entry) => entry.toLowerCase() === normalized);
  return exact ?? null;
}
