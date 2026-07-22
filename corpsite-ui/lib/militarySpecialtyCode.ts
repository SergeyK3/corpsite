export const MILITARY_SPECIALTY_CODE_LENGTH = 7;

export const MILITARY_SPECIALTY_CODE_PATTERN = /^\d{7}$/;

export function sanitizeMilitarySpecialtyCodeInput(raw: string): string {
  return raw.replace(/\D/g, "").slice(0, MILITARY_SPECIALTY_CODE_LENGTH);
}

export function isValidMilitarySpecialtyCode(value: string): boolean {
  const trimmed = value.trim();
  return trimmed === "" || MILITARY_SPECIALTY_CODE_PATTERN.test(trimmed);
}

export function militarySpecialtyCodeValidationMessage(value: string): string | null {
  if (isValidMilitarySpecialtyCode(value)) return null;
  return "Номер ВУС должен содержать ровно 7 цифр.";
}
