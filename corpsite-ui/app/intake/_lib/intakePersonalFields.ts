/** Personal-card fields shared by intake UI, PDF, and derived read-only values. */

export function deriveIntakeSurnameAlphabet(lastName: string | null | undefined): string {
  const trimmed = String(lastName ?? "").trim();
  if (!trimmed) return "";
  const [firstGrapheme] = [...trimmed];
  return firstGrapheme ? firstGrapheme.toLocaleUpperCase("ru-RU") : "";
}

export function normalizeIntakePersonnelNumber(value: string | null | undefined): string {
  return String(value ?? "").trim();
}

export function shouldShowIntakePersonnelNumberField(
  mode: "public" | "hr-on-behalf",
  personnelNumber: string | null | undefined,
): boolean {
  if (mode === "hr-on-behalf") return true;
  return normalizeIntakePersonnelNumber(personnelNumber) !== "";
}

export function isIntakePersonnelNumberEditable(
  mode: "public" | "hr-on-behalf",
  readOnly?: boolean,
): boolean {
  return mode === "hr-on-behalf" && !readOnly;
}

export function reconcileIntakePersonalBlock<
  T extends {
    last_name: string;
    first_name: string;
    middle_name: string;
    birth_date: string;
    birth_place: string;
    gender: string;
    citizenship: string;
    nationality: string;
    personnel_number?: string;
    photo_file_id?: string;
  },
>(personal: T): T {
  return {
    ...personal,
    personnel_number: normalizeIntakePersonnelNumber(personal.personnel_number),
    photo_file_id: String(personal.photo_file_id ?? "").trim(),
  };
}
