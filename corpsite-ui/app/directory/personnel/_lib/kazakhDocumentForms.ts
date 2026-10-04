export type KazakhCase = "dative" | "genitive";
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
  if (/(ұлы|қызы)$/u.test(lower)) return { value: source + (isFront(source) ? "не" : "на"), needsReview: false };
  const ambiguous = /[иуь]$/u.test(lower) || source.includes("-");
  // §26: -ин is always thin; -ов/-ев use the stem's final syllable.
  let harmonyWord = source;
  let forcedFront: boolean | undefined;
  if (/ин$/u.test(lower)) forcedFront = true;
  else if (/(ов|ев)$/u.test(lower)) harmonyWord = source.slice(0, -2);
  // Female surnames keep their written -а; this also gives Маженоваға/-ның.
  else if (/ова$/u.test(lower)) forcedFront = false;
  else if (/ева$/u.test(lower)) forcedFront = true;
  else if (/ина$/u.test(lower)) forcedFront = false;
  const front = isFront(harmonyWord, forcedFront);
  return { value: source + ending(source, form, front), needsReview: ambiguous };
}

export function calculateKazakhPersonForm(
  person: { fio?: unknown; first_name?: unknown; middle_name?: unknown; last_name?: unknown },
  form: KazakhCase,
): CalculatedKazakhForm {
  const first = text(person.first_name);
  const middle = text(person.middle_name);
  const last = text(person.last_name);
  const fallback = text(person.fio).split(/\s+/u).filter(Boolean);
  const parts = last ? [first, middle, last] : [fallback[1] || "", fallback[2] || "", fallback[0] || ""];
  const surname = parts[2];
  const inflected = kazakhInflectWord(surname, form);
  return { value: [parts[0], parts[1], inflected.value].filter(Boolean).join(" "), needsReview: inflected.needsReview };
}

export function calculateKazakhOrgUnitGenitive(name: unknown): CalculatedKazakhForm {
  const source = text(name);
  if (!source) return { value: "", needsReview: true };
  const words = source.split(/\s+/u);
  const last = words.pop() || "";
  const lower = last.toLocaleLowerCase("kk-KZ");
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
