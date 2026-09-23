export const PERSONNEL_ORDER_SIGNATORY_ROLES = ["DIRECTOR", "ACTING_DIRECTOR"] as const;

export type PersonnelOrderSignatoryRole = (typeof PERSONNEL_ORDER_SIGNATORY_ROLES)[number];

const labels: Record<PersonnelOrderSignatoryRole, { kk: string; ru: string }> = {
  DIRECTOR: { kk: "Директоры", ru: "Директор" },
  ACTING_DIRECTOR: { kk: "Директордың міндетін атқарушы", ru: "И. о. директора" },
};

function normalized(value: string | null | undefined): string {
  return String(value || "").toLocaleLowerCase("ru-RU").replace(/[.\s]+/g, " ").trim();
}

/** Accept persisted codes and legacy display values without relying on UI language. */
export function normalizePersonnelOrderSignatoryRole(
  value: string | null | undefined,
): PersonnelOrderSignatoryRole | null {
  const source = normalized(value);
  if (source === "director" || source === "директор" || source === "директоры") return "DIRECTOR";
  if (
    source === "acting_director"
    || source === "и о директора"
    || source === "ио директора"
    || source === "директордың міндетін атқарушы"
  ) return "ACTING_DIRECTOR";
  return null;
}

export function personnelOrderSignatoryRoleLabel(
  role: PersonnelOrderSignatoryRole,
  language: "kk" | "ru",
): string {
  return labels[role][language];
}
