// FILE: corpsite-ui/lib/orgScope.ts

import { apiFetchJson } from "./api";

export const ORG_GROUP_ID_PARAM = "org_group_id";
export const ORG_UNIT_ID_PARAM = "org_unit_id";

export type OrgScopeQuery = {
  org_group_id?: number;
  org_unit_id?: number;
};

export type DepartmentGroupRow = {
  group_id: number;
  group_name: string;
};

export type DepartmentGroupsResponse = {
  items?: DepartmentGroupRow[];
  total?: number;
};

type SearchParamsLike = {
  get(name: string): string | null;
};

export function parsePositiveIntParam(value: string | null | undefined): number | undefined {
  const s = String(value ?? "").trim();
  if (!s || !/^\d+$/.test(s)) return undefined;
  const n = Number(s);
  if (!Number.isSafeInteger(n) || n <= 0) return undefined;
  return n;
}

export function readOrgScopeFromSearchParams(sp: SearchParamsLike): OrgScopeQuery {
  const org_group_id = parsePositiveIntParam(sp.get(ORG_GROUP_ID_PARAM));
  const org_unit_id = parsePositiveIntParam(sp.get(ORG_UNIT_ID_PARAM));
  const out: OrgScopeQuery = {};
  if (org_group_id != null) out.org_group_id = org_group_id;
  if (org_unit_id != null) out.org_unit_id = org_unit_id;
  return out;
}

export function buildOrgScopeQuery(scope: OrgScopeQuery): Record<string, string | undefined> {
  const out: Record<string, string | undefined> = {};
  if (scope.org_group_id != null) out[ORG_GROUP_ID_PARAM] = String(scope.org_group_id);
  if (scope.org_unit_id != null) out[ORG_UNIT_ID_PARAM] = String(scope.org_unit_id);
  return out;
}

export function mergeOrgScopeIntoUrl(
  pathname: string,
  current: URLSearchParams,
  patch: Partial<OrgScopeQuery & { clearOrgGroup?: boolean; clearOrgUnit?: boolean }>,
): string {
  const params = new URLSearchParams(current.toString());

  if (patch.clearOrgGroup) {
    params.delete(ORG_GROUP_ID_PARAM);
  } else if (patch.org_group_id != null) {
    params.set(ORG_GROUP_ID_PARAM, String(patch.org_group_id));
  }

  if (patch.clearOrgUnit) {
    params.delete(ORG_UNIT_ID_PARAM);
  } else if (patch.org_unit_id != null) {
    params.set(ORG_UNIT_ID_PARAM, String(patch.org_unit_id));
  }

  const query = params.toString();
  return query ? `${pathname}?${query}` : pathname;
}

export async function fetchDepartmentGroups(): Promise<DepartmentGroupRow[]> {
  const data = await apiFetchJson<DepartmentGroupsResponse>("/directory/department-groups", {
    query: { limit: 50, offset: 0 },
  });
  const items = Array.isArray(data?.items) ? data.items : [];
  return items
    .map((row) => ({
      group_id: Number(row.group_id),
      group_name: String(row.group_name ?? "").trim(),
    }))
    .filter((row) => Number.isFinite(row.group_id) && row.group_id > 0);
}

export function orgGroupLabel(
  groups: DepartmentGroupRow[],
  orgGroupId: number | undefined,
): string | null {
  if (orgGroupId == null) return null;
  const found = groups.find((g) => g.group_id === orgGroupId);
  return found?.group_name ?? null;
}
