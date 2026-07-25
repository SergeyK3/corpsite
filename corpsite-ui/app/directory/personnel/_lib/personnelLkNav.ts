import { readTaskOrgFiltersFromSearchParams } from "@/lib/taskOrgFilters";

import {
  PERSONNEL_APPLICATION_ID_PARAM,
  PERSONNEL_LK_WORKPLACE_BASE_PATH,
} from "./personnelApplicationsJournalNav";

export const PERSONNEL_LK_REGISTER_PARAM = "register";
export const DEFAULT_PERSONNEL_LK_LIMIT = 50;
export const DEFAULT_PERSONNEL_LK_STATUS = "active" as const;

export type PersonnelLkRecordKindFilter = "" | "employee" | "applicant";
export type PersonnelLkEmployeeStatusFilter = "active" | "inactive" | "all";

export type PersonnelLkRegistryState = {
  q: string;
  record_kind: PersonnelLkRecordKindFilter;
  status: PersonnelLkEmployeeStatusFilter;
  application_status: string;
  limit: number;
  offset: number;
  application_id: number | null;
  org_group_id?: number;
  org_unit_id?: number;
  position_id?: number;
};

const APPLICANTS_REDIRECT_QUERY_KEYS = [
  "q",
  "org_group_id",
  "org_unit_id",
  "position_id",
  PERSONNEL_APPLICATION_ID_PARAM,
  PERSONNEL_LK_REGISTER_PARAM,
] as const;

function parsePositiveInt(value: string | null | undefined): number | null {
  const raw = String(value ?? "").trim();
  if (!raw) return null;
  const numeric = Number(raw);
  if (!Number.isFinite(numeric) || numeric <= 0) return null;
  return Math.trunc(numeric);
}

function normalizeEmployeeStatus(raw: string | null | undefined): PersonnelLkEmployeeStatusFilter {
  const value = String(raw ?? DEFAULT_PERSONNEL_LK_STATUS).trim().toLowerCase();
  if (value === "inactive" || value === "all") return value;
  return "active";
}

function normalizeRecordKind(raw: string | null | undefined): PersonnelLkRecordKindFilter {
  const value = String(raw ?? "").trim().toLowerCase();
  if (value === "employee" || value === "applicant") return value;
  return "";
}

function firstParamValue(
  sp: Record<string, string | string[] | undefined> | URLSearchParams | Pick<URLSearchParams, "get">,
  key: string,
): string | null {
  if (sp instanceof URLSearchParams) {
    return sp.get(key);
  }
  if ("get" in sp && typeof sp.get === "function") {
    return sp.get(key);
  }
  const raw = (sp as Record<string, string | string[] | undefined>)[key];
  if (Array.isArray(raw)) return raw[0] ?? null;
  return raw ?? null;
}

export function parsePersonnelLkRegistryState(
  sp: Pick<URLSearchParams, "get">,
): PersonnelLkRegistryState {
  const org = readTaskOrgFiltersFromSearchParams(sp);
  const limitRaw = Number(sp.get("limit") || DEFAULT_PERSONNEL_LK_LIMIT);
  const offsetRaw = Number(sp.get("offset") || 0);

  return {
    q: sp.get("q")?.trim() || "",
    record_kind: normalizeRecordKind(sp.get("record_kind")),
    status: normalizeEmployeeStatus(sp.get("status")),
    application_status: sp.get("application_status")?.trim() || "",
    limit: Number.isFinite(limitRaw) && limitRaw > 0 ? limitRaw : DEFAULT_PERSONNEL_LK_LIMIT,
    offset: Number.isFinite(offsetRaw) && offsetRaw >= 0 ? offsetRaw : 0,
    application_id: parsePositiveInt(sp.get(PERSONNEL_APPLICATION_ID_PARAM)),
    org_group_id: org.org_group_id,
    org_unit_id: org.org_unit_id,
    position_id: org.position_id,
  };
}

export function buildPersonnelLkRegistryQueryParams(
  state: PersonnelLkRegistryState,
  options?: { includeApplicationId?: boolean; includeRegister?: boolean },
): URLSearchParams {
  const params = new URLSearchParams();
  const includeApplicationId = options?.includeApplicationId !== false;

  if (state.q.trim()) params.set("q", state.q.trim());
  if (state.record_kind) params.set("record_kind", state.record_kind);
  if (state.status !== DEFAULT_PERSONNEL_LK_STATUS) params.set("status", state.status);
  if (state.application_status.trim()) params.set("application_status", state.application_status.trim());
  if (state.org_group_id != null) params.set("org_group_id", String(state.org_group_id));
  if (state.org_unit_id != null) params.set("org_unit_id", String(state.org_unit_id));
  if (state.position_id != null) params.set("position_id", String(state.position_id));
  if (state.limit !== DEFAULT_PERSONNEL_LK_LIMIT) params.set("limit", String(state.limit));
  if (state.offset > 0) params.set("offset", String(state.offset));
  if (includeApplicationId && state.application_id != null) {
    params.set(PERSONNEL_APPLICATION_ID_PARAM, String(state.application_id));
  }
  if (options?.includeRegister) {
    params.set(PERSONNEL_LK_REGISTER_PARAM, "1");
  }

  return params;
}

export function buildPersonnelLkRegistryHref(
  state: PersonnelLkRegistryState,
  options?: { includeApplicationId?: boolean; includeRegister?: boolean },
): string {
  const params = buildPersonnelLkRegistryQueryParams(state, options);
  const qs = params.toString();
  return qs ? `${PERSONNEL_LK_WORKPLACE_BASE_PATH}?${qs}` : PERSONNEL_LK_WORKPLACE_BASE_PATH;
}

export function buildPersonnelLkListLoadKey(state: PersonnelLkRegistryState): string {
  return JSON.stringify({
    q: state.q,
    record_kind: state.record_kind,
    status: state.status,
    application_status: state.application_status,
    limit: state.limit,
    offset: state.offset,
    org_group_id: state.org_group_id ?? null,
    org_unit_id: state.org_unit_id ?? null,
    position_id: state.position_id ?? null,
  });
}

export function migrateApplicantsSearchParamsToLkQuery(
  sp: Record<string, string | string[] | undefined> | URLSearchParams | Pick<URLSearchParams, "get">,
): string {
  const params = new URLSearchParams();
  for (const key of APPLICANTS_REDIRECT_QUERY_KEYS) {
    const value = firstParamValue(sp, key);
    if (value != null && String(value).trim()) {
      params.set(key, String(value).trim());
    }
  }
  return params.toString();
}

export function buildApplicantsRedirectTarget(
  sp: Record<string, string | string[] | undefined> | URLSearchParams | Pick<URLSearchParams, "get">,
): string {
  const qs = migrateApplicantsSearchParamsToLkQuery(sp);
  return qs ? `${PERSONNEL_LK_WORKPLACE_BASE_PATH}?${qs}` : PERSONNEL_LK_WORKPLACE_BASE_PATH;
}
