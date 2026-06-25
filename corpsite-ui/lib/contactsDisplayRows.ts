// FILE: corpsite-ui/lib/contactsDisplayRows.ts

export type ContactItem = {
  contact_id: number;
  person_id?: number | null;
  full_name?: string | null;
  phone?: string | null;
  telegram_username?: string | null;
  telegram_numeric_id?: number | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type PositionSlot = {
  position_id: number;
  name: string;
};

export type WorkingExpertRow = {
  user_id: number;
  person_id?: number | null;
  full_name?: string | null;
  role_name?: string | null;
  role_name_ru?: string | null;
  phone?: string | null;
  telegram_username?: string | null;
  telegram_id?: number | null;
  unit_name?: string | null;
};

export type ContactDisplayRow =
  | { kind: "contact"; item: ContactItem }
  | { kind: "expert"; item: WorkingExpertRow }
  | { kind: "slot"; position_id: number; slot_label: string };

export type ContactMatchKeys = {
  personIds: Set<number>;
  telegramIds: Set<string>;
  normalizedNames: Set<string>;
};

export function normalizeContactLabel(value?: string | null): string {
  return String(value ?? "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .replace(/[ё]/g, "е")
    .trim();
}

export function buildContactMatchKeys(contacts: ContactItem[]): ContactMatchKeys {
  const personIds = new Set<number>();
  const telegramIds = new Set<string>();
  const normalizedNames = new Set<string>();

  for (const contact of contacts) {
    const personId = contact.person_id;
    if (personId != null && Number.isFinite(personId) && personId > 0) {
      personIds.add(personId);
    }

    const telegramId = contact.telegram_numeric_id;
    if (telegramId != null && Number.isFinite(telegramId) && telegramId > 0) {
      telegramIds.add(String(telegramId));
    }

    const name = normalizeContactLabel(contact.full_name);
    if (name) normalizedNames.add(name);
  }

  return { personIds, telegramIds, normalizedNames };
}

export function normalizedNameMatchesKeys(name: string, keys: ContactMatchKeys): boolean {
  const target = normalizeContactLabel(name);
  if (!target) return false;
  if (keys.normalizedNames.has(target)) return true;

  for (const contactName of keys.normalizedNames) {
    if (contactName === target || contactName.includes(target) || target.includes(contactName)) {
      return true;
    }
  }

  return false;
}

export function contactCoversLabel(contacts: ContactItem[], label: string): boolean {
  const keys = buildContactMatchKeys(contacts);
  return normalizedNameMatchesKeys(label, keys);
}

export function workingExpertMatchesContact(expert: WorkingExpertRow, keys: ContactMatchKeys): boolean {
  const personId = expert.person_id;
  if (personId != null && Number.isFinite(personId) && personId > 0 && keys.personIds.has(personId)) {
    return true;
  }

  const telegramId = expert.telegram_id;
  if (telegramId != null && Number.isFinite(telegramId) && telegramId > 0 && keys.telegramIds.has(String(telegramId))) {
    return true;
  }

  const fullName = String(expert.full_name ?? "").trim();
  if (fullName && normalizedNameMatchesKeys(fullName, keys)) {
    return true;
  }

  return false;
}

export function buildDisplayRows(
  contacts: ContactItem[],
  positions: PositionSlot[],
  experts: WorkingExpertRow[],
): ContactDisplayRow[] {
  const rows: ContactDisplayRow[] = contacts.map((item) => ({ kind: "contact", item }));
  const contactKeys = buildContactMatchKeys(contacts);

  for (const expert of experts) {
    if (workingExpertMatchesContact(expert, contactKeys)) continue;
    rows.push({ kind: "expert", item: expert });
  }

  for (const position of positions) {
    if (contactCoversLabel(contacts, position.name)) continue;
    rows.push({ kind: "slot", position_id: position.position_id, slot_label: position.name });
  }

  return rows;
}
