export type KazakhCase = "dative" | "genitive" | "ablative";
export type CalculatedKazakhForm = { value: string; needsReview: boolean };

const FRONT = "әөүіеёэю";
const VOWELS = "аәеёиіоуұүуыэюя";
const SONOR_OR_VOICED = "йлрмнңуызж";
const NASAL = "мнң";
const HARD = "пфкқтсшхцчбвгғд";

function text(value: unknown) { return typeof value === "string" ? value.trim() : ""; }
function lastLetter(value: string) { return value.toLocaleLowerCase("kk-KZ").slice(-1); }
function lastVowel(value: string) {
  for (const char of [...value.toLocaleLowerCase("kk-KZ")].reverse()) if (VOWELS.includes(char)) return char;
  return "";
}
function isFront(value: string, force?: boolean) { return force ?? FRONT.includes(lastVowel(value)); }
function ending(value: string, form: KazakhCase, front: boolean) {
  const last = lastLetter(value);
  const vowelOrSonor = SONOR_OR_VOICED.includes(last) || VOWELS.includes(last);
  if (form === "ablative") return NASAL.includes(last) ? (front ? "нен" : "нан") : HARD.includes(last) ? (front ? "тен" : "тан") : (front ? "ден" : "дан");
  if (form === "dative") return (vowelOrSonor ? (front ? "ге" : "ға") : (front ? "ке" : "қа"));
  if (VOWELS.includes(last) || NASAL.includes(last)) return front ? "нің" : "ның";
  return (SONOR_OR_VOICED.includes(last) ? (front ? "дің" : "дың") : (front ? "тің" : "тың"));
}

/** Calculate a proposal; it never changes source spelling or persists a dictionary form. */
export function kazakhInflectWord(value: string, form: KazakhCase): CalculatedKazakhForm {
  const source = text(value);
  if (!source) return { value: "", needsReview: true };
  const lower = source.toLocaleLowerCase("kk-KZ");
  // Patronymics already carry third-person possession: Сәрсенбайқызына.
  if (form === "dative" && /(ұлы|қызы)$/u.test(lower)) return { value: source + (isFront(source) ? "не" : "на"), needsReview: false };
  const ambiguous = /[иуь]$/u.test(lower) || source.includes("-");
  // §26: -ин is always thin; -ов/-ев use the stem's final syllable.
  let harmonyWord = source;
  let forcedFront: boolean | undefined;
  if (/ин$/u.test(lower)) forcedFront = true;
  else if (/(ов|ев)$/u.test(lower)) harmonyWord = source.slice(0, -2);
  // Female surnames keep their written -а; this also gives Маженоваға/-ның.
  else if (/ова$/u.test(lower)) forcedFront = false;
  else if (/ева$/u.test(lower)) forcedFront = false;
  else if (/ина$/u.test(lower)) forcedFront = false;
  const front = isFront(harmonyWord, forcedFront);
  return { value: source + ending(source, form, front), needsReview: ambiguous };
}

type KazakhPersonSource = { fio?: unknown; full_name?: unknown; first_name?: unknown; middle_name?: unknown; last_name?: unknown };
type DocumentNameParts = { first: string; middle: string; last: string };
const PATRONYMIC = /(?:ович|евич|ич|овна|евна|ична|ұлы|қызы)$/iu;
const SURNAME = /(?:ов|ев|ин|ын|ова|ева|ина|ына|ский|цкий|ская|цкая)$/iu;

/** Source FIO is unchanged; an ambiguous display order is never guessed. */
function documentNameParts(person: KazakhPersonSource): DocumentNameParts | null {
  const first = text(person.first_name), middle = text(person.middle_name), last = text(person.last_name);
  if (first && last) return { first, middle, last };
  const parts = text(person.fio || person.full_name).split(/\s+/u).filter(Boolean);
  if (parts.length === 3) {
    if (SURNAME.test(parts[0]) && PATRONYMIC.test(parts[2]) && !PATRONYMIC.test(parts[1]))
      return { first: parts[1], middle: parts[2], last: parts[0] };
    if (PATRONYMIC.test(parts[1]) && SURNAME.test(parts[2]) && !SURNAME.test(parts[0]))
      return { first: parts[0], middle: parts[1], last: parts[2] };
  }
  if (parts.length === 2) {
    if (SURNAME.test(parts[0]) && !SURNAME.test(parts[1]) && /^[\p{L}]{2,}$/u.test(parts[1])) return { first: parts[1], middle: "", last: parts[0] };
    if (SURNAME.test(parts[1]) && !SURNAME.test(parts[0]) && /^[\p{L}]{2,}$/u.test(parts[0])) return { first: parts[0], middle: "", last: parts[1] };
  }
  return null;
}

export function calculateKazakhDocumentName(person: KazakhPersonSource): CalculatedKazakhForm {
  const parts = documentNameParts(person);
  return parts ? { value: [parts.first, parts.middle, parts.last].filter(Boolean).join(" "), needsReview: false }
    : { value: "", needsReview: true };
}

export function calculateKazakhPersonForm(person: KazakhPersonSource, form: KazakhCase): CalculatedKazakhForm {
  const parts = documentNameParts(person);
  if (!parts) return { value: "", needsReview: true };
  const inflected = kazakhInflectWord(parts.last, form);
  return { value: [parts.first, parts.middle, inflected.value].filter(Boolean).join(" "), needsReview: inflected.needsReview };
}

export function calculateKazakhOrgUnitGenitive(name: unknown): CalculatedKazakhForm {
  const source = text(name);
  if (!source) return { value: "", needsReview: true };
  const words = source.split(/\s+/u);
  const last = words.pop() || "";
  const lower = last.toLocaleLowerCase("kk-KZ");
  if (/(ның|нің|дың|дің|тың|тің)$/u.test(lower)) return {value:source,needsReview:false};
  // Third-person possessive titles take -ның/-нің after their possessive ending.
  if (/сы$/u.test(lower)) words.push(last + "ның");
  else if (/сі$/u.test(lower)) words.push(last + "нің");
  else words.push(kazakhInflectWord(last, "genitive").value);
  return { value: words.join(" "), needsReview: source.includes("-") || /[иуь]$/u.test(lower) };
}

export function firstNonEmpty(...values: unknown[]) { return values.map(text).find(Boolean) || ""; }

/** Third-person possession, not translation: https://emle.kz/kz/rule?id=125.
 * Calculated catalogue titles remain editable proposals, never saved forms.
 */
export function calculateKazakhPositionPossessive(name: unknown): CalculatedKazakhForm {
  const source = text(name);
  if (!source) return { value: "", needsReview: true };
  const words = source.split(/\s+/u);
  const last = words.pop() || "";
  const lower = last.toLocaleLowerCase("kk-KZ");
  // Compound titles may already carry possession: шаруа бикесі, бөлім бастығы.
  if (/[сғгқкрлмн][ыі]$/u.test(lower)) return { value: source, needsReview: true };
  const front = isFront(last);
  const suffix = VOWELS.includes(lastLetter(last)) ? (front ? "сі" : "сы") : (front ? "і" : "ы");
  const voiced = /[қкп]$/u.test(lower) && [...lower].filter(c => VOWELS.includes(c)).length > 1
    ? last.slice(0, -1) + ({ қ: "ғ", к: "г", п: "б" }[lastLetter(last)] || lastLetter(last)) : last;
  words.push(voiced + suffix);
  return { value: words.join(" "), needsReview: true };
}
