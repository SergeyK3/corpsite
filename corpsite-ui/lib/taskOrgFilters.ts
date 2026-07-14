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

export function normalizeOrgGroupId(value: number | string | null | undefined): number | null {
  if (value == null) return null;
  if (typeof value === "number") {
    return Number.isFinite(value) && value > 0 ? Math.trunc(value) : null;
  }
  const trimmed = String(value).trim();
  if (!trimmed || !/^\d+$/.test(trimmed)) return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) && parsed > 0 ? Math.trunc(parsed) : null;
}

export function filterOrgUnitOptionsForGroup(
  options: readonly OrgUnitSelectOption[],
  orgGroupId: number | string | undefined,
): OrgUnitSelectOption[] {
  const targetGroupId = normalizeOrgGroupId(orgGroupId);
  if (targetGroupId == null) return [...options];
  return options.filter((opt) => normalizeOrgGroupId(opt.group_id) === targetGroupId);
}

export function isOrgUnitAllowedForGroup(
  orgUnitId: number | undefined,
  orgGroupId: number | string | undefined,
  options: readonly OrgUnitSelectOption[],
): boolean {
  if (orgUnitId == null) return true;
  const targetGroupId = normalizeOrgGroupId(orgGroupId);
  if (targetGroupId == null) return options.some((opt) => opt.unit_id === orgUnitId);
  return options.some(
    (opt) => opt.unit_id === orgUnitId && normalizeOrgGroupId(opt.group_id) === targetGroupId,
  );
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

/** Matches backend GET /directory/positions max limit. */
export const GLOBAL_POSITIONS_CATALOG_LIMIT = 1000;

export type PersonnelOrderPositionSelectGroup = {
  key: "used_in_unit" | "all_positions";
  label: string;
  items: TaskOrgFilterOption[];
};

export const PERSONNEL_ORDER_POSITION_GROUP_LABELS = {
  usedInUnit: "Используются в подразделении",
  allPositions: "Все должности",
} as const;

/**
 * Merge scoped (used in unit) and global catalog positions for personnel order editor.
 * Scoped items stay first; dedupe strictly by position_id; preserve duplicate names.
 */
export function buildPersonnelOrderPositionSelectGroups(
  scoped: readonly TaskOrgFilterOption[],
  global: readonly TaskOrgFilterOption[],
): PersonnelOrderPositionSelectGroup[] {
  const seen = new Set<number>();
  const usedInUnit: TaskOrgFilterOption[] = [];

  for (const option of scoped) {
    if (seen.has(option.id)) continue;
    seen.add(option.id);
    usedInUnit.push(option);
  }

  const rest: TaskOrgFilterOption[] = [];
  for (const option of global) {
    if (seen.has(option.id)) continue;
    seen.add(option.id);
    rest.push(option);
  }
  rest.sort((a, b) => a.label.localeCompare(b.label, "ru"));

  const groups: PersonnelOrderPositionSelectGroup[] = [];
  if (usedInUnit.length > 0) {
    groups.push({
      key: "used_in_unit",
      label: PERSONNEL_ORDER_POSITION_GROUP_LABELS.usedInUnit,
      items: usedInUnit,
    });
  }
  if (rest.length > 0) {
    groups.push({
      key: "all_positions",
      label: PERSONNEL_ORDER_POSITION_GROUP_LABELS.allPositions,
      items: rest,
    });
  }
  return groups;
}

export function flattenPersonnelOrderPositionGroups(
  groups: readonly PersonnelOrderPositionSelectGroup[],
): TaskOrgFilterOption[] {
  return groups.flatMap((group) => group.items);
}

export async function loadGlobalPositionCatalog(
  limit: number = GLOBAL_POSITIONS_CATALOG_LIMIT,
): Promise<TaskOrgFilterOption[]> {
  const body = await apiFetchJson<{ items?: PositionRowDto[] }>("/directory/positions", {
    query: { limit, offset: 0 },
  });
  const items = Array.isArray(body?.items) ? body.items : [];
  return normalizePositionOptions(items);
}

let globalPositionCatalogCache: TaskOrgFilterOption[] | null = null;
let globalPositionCatalogPromise: Promise<TaskOrgFilterOption[]> | null = null;

/** Cached global catalog — reused across org-unit changes within one editor session. */
export async function loadGlobalPositionCatalogCached(
  limit: number = GLOBAL_POSITIONS_CATALOG_LIMIT,
): Promise<TaskOrgFilterOption[]> {
  if (globalPositionCatalogCache) return globalPositionCatalogCache;
  if (!globalPositionCatalogPromise) {
    globalPositionCatalogPromise = loadGlobalPositionCatalog(limit).then((items) => {
      globalPositionCatalogCache = items;
      return items;
    });
  }
  return globalPositionCatalogPromise;
}

/** Test helper — reset module-level global catalog cache. */
export function resetGlobalPositionCatalogCache(): void {
  globalPositionCatalogCache = null;
  globalPositionCatalogPromise = null;
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
