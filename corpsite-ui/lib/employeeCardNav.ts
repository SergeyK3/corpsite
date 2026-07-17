// FILE: corpsite-ui/lib/employeeCardNav.ts
import { normalizeReturnTo, RETURN_TO_QUERY_PARAM } from "./taskNav";

/** Navigation helpers for the unified HR dossier page (user-facing «Кадровая карточка-досье»). */

export type EmployeeCardSectionId =
  | "general"
  | "assignment"
  | "access"
  | "orders"
  | "onboarding"
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
  { id: "onboarding", title: "Адаптация" },
  { id: "history", title: "История кадровых событий" },
];

export const EMPLOYEE_CARD_DEFAULT_SECTION: EmployeeCardSectionId = "assignment";

export type BuildEmployeeCardHrefOptions = {
  section?: EmployeeCardSectionId;
  provisionAccount?: boolean;
  returnTo?: string | null;
};

function normalizeEmployeeId(employeeId: string | number): string {
  return encodeURIComponent(String(employeeId).trim());
}

export function buildEmployeeCardHref(
  employeeId: string | number,
  options: BuildEmployeeCardHrefOptions = {},
): string {
  return buildPersonalCardHref({ employeeId }, options);
}

export type BuildPersonalCardHrefOptions = BuildEmployeeCardHrefOptions;

export function buildPersonalCardHref(
  subject: { personId?: string | number; employeeId?: string | number },
  options: BuildPersonalCardHrefOptions = {},
): string {
  const personId = subject.personId != null ? normalizeEmployeeId(subject.personId) : "";
  const employeeId = subject.employeeId != null ? normalizeEmployeeId(subject.employeeId) : "";
  const base = personId
    ? `/directory/personnel/persons/${personId}/card`
    : `/directory/personnel/employees/${employeeId}/card`;
  const params = new URLSearchParams();

  if (options.section && options.section !== EMPLOYEE_CARD_DEFAULT_SECTION) {
    params.set("section", options.section);
  }
  if (options.provisionAccount) {
    params.set("provisionAccount", "1");
  }
  const returnTo = normalizeReturnTo(options.returnTo);
  if (returnTo) {
    params.set(RETURN_TO_QUERY_PARAM, returnTo);
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
