import { savedRussianEmployeeNameForm } from "./personnelOrderRussianWording";

export const TRANSFER_ACCUSATIVE_WARNING = "Не удалось надёжно определить пол или склонить ФИО в винительном падеже (RU). Проверьте ФИО и заполните поле вручную.";

type Gender = "male" | "female";
const consonant = /[бвгджзклмнпрстфхцчшщ]$/iu;
const word = /^[А-ЯЁа-яёӘәҒғҚқҢңӨөҰұҮүҺһІі]+(?:-[А-ЯЁа-яёӘәҒғҚқҢңӨөҰұҮүҺһІі]+)*$/u;
const clean = (value: unknown): string => typeof value === "string" ? value.trim() : "";

function explicitGender(value: unknown): Gender | null {
  const normalized = clean(value).toLocaleLowerCase("ru-RU");
  if (["m", "male", "м", "мужской", "мужчина"].includes(normalized)) return "male";
  if (["f", "female", "ж", "женский", "женщина"].includes(normalized)) return "female";
  return null;
}

function patronymicGender(middle: string): Gender | null {
  if (/(?:овна|евна|ёвна|ична|кызы|қызы)$/iu.test(middle)) return "female";
  if (/(?:ич|оглы|ұлы)$/iu.test(middle)) return "male";
  return null;
}

function surname(part: string, gender: Gender): string | null {
  // These endings are indeclinable in Russian for either gender.
  if (/(?:их|ых|ко|енко)$/iu.test(part) || /[оеёиуыэю]$/iu.test(part)
      || /^(?:Дюма|Золя|Делакруа)$/iu.test(part)) return part;
  if (gender === "female") {
    if (/(?:ова|ева|ёва|ина|ына)$/iu.test(part)) return part.slice(0, -1) + "у";
    if (/ая$/iu.test(part)) return part.slice(0, -2) + "ую";
    if (/яя$/iu.test(part)) return part.slice(0, -2) + "юю";
    if (consonant.test(part) || /[йь]$/iu.test(part)) return part;
  } else {
    if (/(?:ский|цкий|ый|ой)$/iu.test(part)) return part.slice(0, -2) + "ого";
    // Do not guess fleeting vowels (e.g. Боец), or soft-adjective surnames.
    if (/(?:ец|ек|ок|ень|ий)$/iu.test(part)) return null;
    if (consonant.test(part)) return part + "а";
    if (/[йь]$/iu.test(part)) return part.slice(0, -1) + "я";
  }
  return null;
}

function givenName(part: string, gender: Gender): string | null {
  const irregular: Record<string, string> = { павел: "Павла", лев: "Льва", пётр: "Петра", петр: "Петра" };
  if (gender === "male" && irregular[part.toLocaleLowerCase("ru-RU")]) {
    const result = irregular[part.toLocaleLowerCase("ru-RU")];
    return part === part.toLocaleUpperCase("ru-RU") ? result.toLocaleUpperCase("ru-RU") : result;
  }
  if (/^Николя$/iu.test(part)) return part;
  if (/а$/iu.test(part)) return part.slice(0, -1) + "у";
  if (/я$/iu.test(part)) return part.slice(0, -1) + "ю";
  // Female names such as Гульжан, Ассель and Любовь retain their source form.
  if (gender === "female" && (consonant.test(part) || /[йь]$/iu.test(part))) return part;
  if (gender === "male" && /[йь]$/iu.test(part)) return part.slice(0, -1) + "я";
  if (gender === "male" && consonant.test(part)) return part + "а";
  if (/[оеёиуыэю]$/iu.test(part)) return part;
  return null;
}

function patronymic(part: string, gender: Gender): string | null {
  if (/(?:оглы|ұлы|кызы|қызы)$/iu.test(part)) return part;
  if (gender === "female" && /(?:овна|евна|ёвна|ична)$/iu.test(part)) return part.slice(0, -1) + "у";
  if (gender === "male" && /ич$/iu.test(part)) return part + "а";
  return null;
}

function compound(part: string, decline: (word: string) => string | null): string | null {
  const result = part.split("-").map(decline);
  return result.some(value => value === null) ? null : result.join("-");
}

/** Only a TRANSFER form suggestion. Saved/manual forms always win; never use a saved dative. */
export function russianTransferAccusative(employee: unknown): string {
  const saved = savedRussianEmployeeNameForm(employee, "accusative");
  if (saved) return saved;
  if (!employee || typeof employee !== "object") return "";
  const row = employee as Record<string, unknown>;
  const structured = Boolean(clean(row.last_name) || clean(row.first_name));
  const parts = structured
    ? [clean(row.last_name), clean(row.first_name), clean(row.middle_name)].filter((value, index) => index < 2 || value)
    : clean(row.fio || row.full_name).split(/\s+/u);
  if (parts.length < 2 || parts.length > 3 || parts.some(part => !word.test(part) || part.split("-").some(piece => piece.length < 2))) return "";
  const [last, first, middle = ""] = parts;
  const fromPatronymic = patronymicGender(middle);
  const genderValues = [row.gender, row.sex].map(explicitGender).filter((value): value is Gender => value !== null);
  if (new Set(genderValues).size > 1) return "";
  const explicit = genderValues[0];
  if (explicit && fromPatronymic && explicit !== fromPatronymic) return "";
  const gender = explicit || fromPatronymic;
  if (!gender) return "";
  const result = [compound(last, value => surname(value, gender)), compound(first, value => givenName(value, gender))];
  if (middle) result.push(patronymic(middle, gender));
  return result.some(value => value === null) ? "" : result.map((value, index) =>
    parts[index] === parts[index].toLocaleUpperCase("ru-RU") ? value!.toLocaleUpperCase("ru-RU") : value,
  ).join(" ");
}
