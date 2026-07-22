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

/** Canonical UEPC route by `person_id` (preferred entry when person key is known). */
export function buildPersonCardHref(
  personId: string | number,
  options: BuildPersonalCardHrefOptions = {},
): string {
  return buildPersonalCardHref({ personId }, options);
}

export type BuildPersonalCardHrefOptions = BuildEmployeeCardHrefOptions;

function normalizePositiveIntRouteId(value: string | null | undefined): string | null {
  const trimmed = String(value ?? "").trim();
  if (!trimmed) return null;
  const numeric = Number(trimmed);
  if (!Number.isFinite(numeric) || numeric <= 0 || !Number.isInteger(numeric)) return null;
  return trimmed;
}

/** Validates dynamic route segment for `/persons/{person_id}/card`. */
export function parseRoutePersonId(value: string | null | undefined): string | null {
  return normalizePositiveIntRouteId(value);
}

/** Validates dynamic route segment for `/employees/{employee_id}/card` compatibility route. */
export function parseRouteEmployeeId(value: string | null | undefined): string | null {
  return normalizePositiveIntRouteId(value);
}

/** Preserve supported legacy card query params when redirecting employee → person route. */
export function buildPersonCardHrefFromLegacySearchParams(
  personId: string | number,
  searchParams: Pick<URLSearchParams, "get">,
): string {
  const sectionRaw = searchParams.get("section");
  const section = sectionRaw ? parseEmployeeCardSection(sectionRaw) : undefined;
  const provisionAccount = searchParams.get("provisionAccount") === "1";
  const returnTo = searchParams.get(RETURN_TO_QUERY_PARAM);

  return buildPersonCardHref(personId, {
    section:
      section && section !== EMPLOYEE_CARD_DEFAULT_SECTION ? section : undefined,
    provisionAccount: provisionAccount || undefined,
    returnTo,
  });
}

const LEGACY_CARD_QUERY_KEYS = ["section", "provisionAccount", RETURN_TO_QUERY_PARAM] as const;

/** Serialize App Router page searchParams for employee-card compatibility redirect. */
export function buildLegacyCardQueryStringFromPageSearchParams(
  searchParams: Record<string, string | string[] | undefined>,
): string {
  const params = new URLSearchParams();
  for (const key of LEGACY_CARD_QUERY_KEYS) {
    const raw = searchParams[key];
    const value = Array.isArray(raw) ? raw[0] : raw;
    if (value != null && String(value).trim()) {
      params.set(key, String(value).trim());
    }
  }
  return params.toString();
}

export function legacyCardQueryStringToSearchParams(queryString: string): URLSearchParams {
  return new URLSearchParams(queryString);
}

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
