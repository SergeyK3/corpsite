// FILE: corpsite-ui/lib/taskOrgFilters.ts

import { apiFetchJson } from "./api";
import {
  ORG_GROUP_ID_PARAM,
  ORG_UNIT_ID_PARAM,
  parsePositiveIntParam,
  readOrgScopeFromSearchParams,
  type OrgScopeQuery,
} from "./orgScope";
import type { OrgUnitSelectOption } from "./orgUnitsSelect";
import type { TaskScope } from "./types";

export const TASK_POSITION_ID_PARAM = "position_id";

export type TaskOrgFilterState = OrgScopeQuery & {
  position_id?: number;
};

export type TaskOrgFilterOption = {
  id: number;
  label: string;
};

export type PositionRowDto = {
  position_id?: number | null;
  id?: number | null;
  name?: string | null;
};

export const TASK_ORG_FILTER_RESET_PARAM_KEYS = [
  ORG_GROUP_ID_PARAM,
  ORG_UNIT_ID_PARAM,
  TASK_POSITION_ID_PARAM,
  "offset",
] as const;

export function readTaskOrgFiltersFromSearchParams(sp: {
  get(name: string): string | null;
}): TaskOrgFilterState {
  const scope = readOrgScopeFromSearchParams(sp);
  const position_id = parsePositiveIntParam(sp.get(TASK_POSITION_ID_PARAM));
  return {
    ...scope,
    ...(position_id != null ? { position_id } : {}),
  };
}

export function hasActiveTaskOrgFilters(state: TaskOrgFilterState): boolean {
  return (
    state.org_group_id != null ||
    state.org_unit_id != null ||
    state.position_id != null
  );
}

export function shouldShowTaskOrgFilters(options: {
  isSystemAdmin: boolean;
  taskScope: TaskScope;
}): boolean {
  return options.isSystemAdmin && options.taskScope === "team";
}

export function filterOrgUnitOptionsForGroup(
  options: readonly OrgUnitSelectOption[],
  orgGroupId: number | undefined,
): OrgUnitSelectOption[] {
  if (orgGroupId == null) return [...options];
  return options.filter((opt) => opt.group_id === orgGroupId);
}

export function isOrgUnitAllowedForGroup(
  orgUnitId: number | undefined,
  orgGroupId: number | undefined,
  options: readonly OrgUnitSelectOption[],
): boolean {
  if (orgUnitId == null) return true;
  if (orgGroupId == null) return options.some((opt) => opt.unit_id === orgUnitId);
  return options.some((opt) => opt.unit_id === orgUnitId && opt.group_id === orgGroupId);
}

export function isPositionAllowedInOptions(
  positionId: number | undefined,
  options: readonly TaskOrgFilterOption[],
): boolean {
  if (positionId == null) return true;
  return options.some((opt) => opt.id === positionId);
}

export function positionIdOf(row: PositionRowDto): number | null {
  const id = Number(row.position_id ?? row.id ?? 0);
  return Number.isFinite(id) && id > 0 ? id : null;
}

export function normalizePositionOptions(rows: readonly PositionRowDto[]): TaskOrgFilterOption[] {
  const seen = new Set<number>();
  const out: TaskOrgFilterOption[] = [];

  for (const row of rows) {
    const id = positionIdOf(row);
    if (id == null || seen.has(id)) continue;
    seen.add(id);
    const name = String(row.name ?? "").trim();
    out.push({ id, label: name || `#${id}` });
  }

  return out.sort((a, b) => a.label.localeCompare(b.label, "ru"));
}

export async function loadScopedPositionOptions(scope: {
  org_group_id?: number;
  org_unit_id?: number;
}): Promise<TaskOrgFilterOption[]> {
  const query: Record<string, string | number | undefined> = {
    limit: 500,
    offset: 0,
  };
  if (scope.org_group_id != null) query.org_group_id = scope.org_group_id;
  if (scope.org_unit_id != null) query.org_unit_id = scope.org_unit_id;

  const body = await apiFetchJson<{ items?: PositionRowDto[] }>("/directory/positions", {
    query,
  });
  const items = Array.isArray(body?.items) ? body.items : [];
  return normalizePositionOptions(items);
}

export function buildTaskOrgFiltersResetUrl(
  pathname: string,
  current: URLSearchParams,
): string {
  const params = new URLSearchParams(current.toString());
  for (const key of TASK_ORG_FILTER_RESET_PARAM_KEYS) {
    params.delete(key);
  }
  const query = params.toString();
  return query ? `${pathname}?${query}` : pathname;
}
