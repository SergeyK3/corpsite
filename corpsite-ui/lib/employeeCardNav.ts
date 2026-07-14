// FILE: corpsite-ui/lib/employeeCardNav.ts
/** Navigation helpers for the unified HR Employee Card (user-facing «Карточка сотрудника»). */

export type EmployeeCardSectionId =
  | "general"
  | "assignment"
  | "access"
  | "orders"
  | "history";

export type EmployeeCardSectionDef = {
  id: EmployeeCardSectionId;
  title: string;
};

export const EMPLOYEE_CARD_SECTIONS: EmployeeCardSectionDef[] = [
  { id: "general", title: "Общие сведения" },
  { id: "assignment", title: "Текущее назначение" },
  { id: "access", title: "Доступ" },
  { id: "orders", title: "Кадровые приказы" },
  { id: "history", title: "История кадровых событий" },
];

export const EMPLOYEE_CARD_DEFAULT_SECTION: EmployeeCardSectionId = "assignment";

export type BuildEmployeeCardHrefOptions = {
  section?: EmployeeCardSectionId;
  provisionAccount?: boolean;
};

function normalizeEmployeeId(employeeId: string | number): string {
  return encodeURIComponent(String(employeeId).trim());
}

export function buildEmployeeCardHref(
  employeeId: string | number,
  options: BuildEmployeeCardHrefOptions = {},
): string {
  const base = `/directory/personnel/employees/${normalizeEmployeeId(employeeId)}/card`;
  const params = new URLSearchParams();

  if (options.section && options.section !== EMPLOYEE_CARD_DEFAULT_SECTION) {
    params.set("section", options.section);
  }
  if (options.provisionAccount) {
    params.set("provisionAccount", "1");
  }

  const qs = params.toString();
  return qs ? `${base}?${qs}` : base;
}

export function buildEmployeeCardAccessHref(employeeId: string | number): string {
  return buildEmployeeCardHref(employeeId, { section: "access", provisionAccount: true });
}

export function parseEmployeeCardSection(
  value: string | null | undefined,
): EmployeeCardSectionId {
  const normalized = String(value || "").trim().toLowerCase();
  const known = EMPLOYEE_CARD_SECTIONS.find((s) => s.id === normalized);
  return known?.id ?? EMPLOYEE_CARD_DEFAULT_SECTION;
}
