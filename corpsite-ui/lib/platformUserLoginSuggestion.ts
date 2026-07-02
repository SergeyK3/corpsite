/** OPS-028 — Platform User login suggestion ({surname}.{initials}). */

export const MAX_PLATFORM_USER_LOGIN_LENGTH = 64;

const CYRILLIC_TO_LATIN: Record<string, string> = {
  а: "a",
  б: "b",
  в: "v",
  г: "g",
  д: "d",
  е: "e",
  ё: "e",
  ж: "zh",
  з: "z",
  и: "i",
  й: "y",
  к: "k",
  л: "l",
  м: "m",
  н: "n",
  о: "o",
  п: "p",
  р: "r",
  с: "s",
  т: "t",
  у: "u",
  ф: "f",
  х: "h",
  ц: "ts",
  ч: "ch",
  ш: "sh",
  щ: "sch",
  ъ: "",
  ы: "y",
  ь: "",
  э: "e",
  ю: "yu",
  я: "ya",
};

const LOGIN_ALLOWED_CHARS = /[^a-z0-9._-]+/g;

function transliterateChar(ch: string): string {
  return CYRILLIC_TO_LATIN[ch] ?? ch;
}

export function transliterateCyrillic(text: string): string {
  return String(text || "")
    .toLowerCase()
    .split("")
    .map((ch) => transliterateChar(ch))
    .join("");
}

function sanitizeLoginPart(value: string): string {
  return transliterateCyrillic(value).replace(LOGIN_ALLOWED_CHARS, "");
}

function parseFioTokens(fullName: string): string[] {
  return String(fullName || "")
    .trim()
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean);
}

/**
 * Suggest login as `{translit_surname}.{initials}` per OPS-028.
 * FIO order: Surname FirstName [Patronymic].
 */
export function suggestPlatformUserLogin(fullName: string): string {
  const parts = parseFioTokens(fullName);
  if (parts.length === 0) return "";

  const surname = sanitizeLoginPart(parts[0] ?? "");
  if (!surname) return "";

  const initials: string[] = [];
  if (parts.length >= 2) {
    const firstInitial = sanitizeLoginPart((parts[1] ?? "").slice(0, 1));
    if (firstInitial) initials.push(firstInitial);
  }
  if (parts.length >= 3) {
    const patronymicInitial = sanitizeLoginPart((parts[2] ?? "").slice(0, 1));
    if (patronymicInitial) initials.push(patronymicInitial);
  }

  const login =
    initials.length > 0 ? `${surname}.${initials.join("")}` : surname;

  return login.slice(0, MAX_PLATFORM_USER_LOGIN_LENGTH);
}
