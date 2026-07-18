import { normalizeReturnTo, RETURN_TO_QUERY_PARAM } from "@/lib/taskNav";
import { readTaskOrgFiltersFromSearchParams } from "@/lib/taskOrgFilters";

/** HR workplace journal — единая вкладка «Претенденты». */
export const PERSONNEL_APPLICANTS_WORKPLACE_BASE_PATH = "/directory/personnel/applicants";

export const PERSONNEL_APPLICATION_ID_PARAM = "application_id";
export const PERSONNEL_APPLICATION_VIEW_PARAM = "view";
export const JOURNAL_VIEW_ACTIVE = "active";
export const JOURNAL_VIEW_ARCHIVE = "archive";
export const DEFAULT_JOURNAL_LIMIT = 50;
export const DEFAULT_JOURNAL_SORT = "application_received_at_desc";
export const DEFAULT_JOURNAL_VIEW = JOURNAL_VIEW_ACTIVE;

export type PersonnelApplicationsJournalView = typeof JOURNAL_VIEW_ACTIVE | typeof JOURNAL_VIEW_ARCHIVE;

export type PersonnelApplicationsJournalState = {
  q: string;
  sort: string;
  view: PersonnelApplicationsJournalView;
  limit: number;
  offset: number;
  application_id: number | null;
  org_group_id?: number;
  org_unit_id?: number;
  position_id?: number;
};

function parsePositiveInt(value: string | null | undefined): number | null {
  const raw = String(value ?? "").trim();
  if (!raw) return null;
  const numeric = Number(raw);
  if (!Number.isFinite(numeric) || numeric <= 0) return null;
  return Math.trunc(numeric);
}

export function parsePersonnelApplicationsJournalState(
  sp: Pick<URLSearchParams, "get">,
): PersonnelApplicationsJournalState {
  const org = readTaskOrgFiltersFromSearchParams(sp);
  const limitRaw = Number(sp.get("limit") || DEFAULT_JOURNAL_LIMIT);
  const offsetRaw = Number(sp.get("offset") || 0);
  const applicationId = parsePositiveInt(sp.get(PERSONNEL_APPLICATION_ID_PARAM));
  const viewRaw = sp.get(PERSONNEL_APPLICATION_VIEW_PARAM)?.trim();
  const view =
    viewRaw === JOURNAL_VIEW_ARCHIVE ? JOURNAL_VIEW_ARCHIVE : JOURNAL_VIEW_ACTIVE;

  return {
    q: sp.get("q")?.trim() || "",
    sort: sp.get("sort")?.trim() || DEFAULT_JOURNAL_SORT,
    view,
    limit: Number.isFinite(limitRaw) && limitRaw > 0 ? limitRaw : DEFAULT_JOURNAL_LIMIT,
    offset: Number.isFinite(offsetRaw) && offsetRaw >= 0 ? offsetRaw : 0,
    application_id: applicationId,
    org_group_id: org.org_group_id,
    org_unit_id: org.org_unit_id,
    position_id: org.position_id,
  };
}

export function buildPersonnelApplicationsJournalQueryParams(
  state: PersonnelApplicationsJournalState,
  options?: { includeApplicationId?: boolean },
): URLSearchParams {
  const params = new URLSearchParams();
  const includeApplicationId = options?.includeApplicationId !== false;

  if (state.q.trim()) params.set("q", state.q.trim());
  if (state.view === JOURNAL_VIEW_ARCHIVE) params.set(PERSONNEL_APPLICATION_VIEW_PARAM, JOURNAL_VIEW_ARCHIVE);
  if (state.sort && state.sort !== DEFAULT_JOURNAL_SORT) params.set("sort", state.sort);
  if (state.org_group_id != null) params.set("org_group_id", String(state.org_group_id));
  if (state.org_unit_id != null) params.set("org_unit_id", String(state.org_unit_id));
  if (state.position_id != null) params.set("position_id", String(state.position_id));
  if (state.limit !== DEFAULT_JOURNAL_LIMIT) params.set("limit", String(state.limit));
  if (state.offset > 0) params.set("offset", String(state.offset));
  if (includeApplicationId && state.application_id != null) {
    params.set(PERSONNEL_APPLICATION_ID_PARAM, String(state.application_id));
  }

  return params;
}

export function buildPersonnelApplicationsJournalHref(
  state: PersonnelApplicationsJournalState,
  options?: { includeApplicationId?: boolean; basePath?: string },
): string {
  const basePath = options?.basePath ?? PERSONNEL_APPLICANTS_WORKPLACE_BASE_PATH;
  const params = buildPersonnelApplicationsJournalQueryParams(state, options);
  const qs = params.toString();
  return qs ? `${basePath}?${qs}` : basePath;
}

export function buildPersonnelApplicationsListLoadKey(state: PersonnelApplicationsJournalState): string {
  return JSON.stringify({
    q: state.q,
    sort: state.sort,
    view: state.view,
    limit: state.limit,
    offset: state.offset,
    org_group_id: state.org_group_id ?? null,
    org_unit_id: state.org_unit_id ?? null,
    position_id: state.position_id ?? null,
  });
}

export function buildPersonalCardHrefFromJournal(
  personId: number | string,
  journalReturnHref: string,
): string {
  const base = `/directory/personnel/persons/${encodeURIComponent(String(personId).trim())}/card`;
  const returnTo = normalizeReturnTo(journalReturnHref);
  if (!returnTo) return base;
  const params = new URLSearchParams();
  params.set(RETURN_TO_QUERY_PARAM, returnTo);
  return `${base}?${params.toString()}`;
}

export function resolvePersonalCardBackHref(returnTo: string | null | undefined): string {
  return normalizeReturnTo(returnTo) ?? "/directory/staff";
}

export function isPersonnelApplicationsJournalReturnHref(href: string | null | undefined): boolean {
  const normalized = normalizeReturnTo(href);
  if (!normalized) return false;
  return (
    normalized === PERSONNEL_APPLICANTS_WORKPLACE_BASE_PATH ||
    normalized.startsWith(`${PERSONNEL_APPLICANTS_WORKPLACE_BASE_PATH}?`)
  );
}

export function resolvePersonnelApplicationsJournalBackLabel(
  returnTo: string | null | undefined,
): string {
  const normalized = normalizeReturnTo(returnTo);
  if (!normalized) return "Назад к персоналу";
  if (isPersonnelApplicationsJournalReturnHref(normalized)) {
    return "Назад к претендентам";
  }
  return "Назад";
}
