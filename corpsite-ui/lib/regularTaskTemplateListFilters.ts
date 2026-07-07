// FILE: corpsite-ui/lib/regularTaskTemplateListFilters.ts

import type { TemplateFormExecutorRoleOption } from "@/app/regular-tasks/_components/TemplateForm";

import { ORG_GROUP_ID_PARAM, ORG_UNIT_ID_PARAM } from "./orgScope";
import type { OrgUnitSelectOption } from "./orgUnitsSelect";
import { filterOrgUnitOptionsForGroup, isOrgUnitAllowedForGroup } from "./taskOrgFilters";

export type TemplateExecutorRoleSource = {
  executor_role_id?: number | null;
  executor_role_name?: string | null;
  executor_role_code?: string | null;
};

export type RegularTaskTemplateListFilters = {
  org_group_id?: number;
  org_unit_id?: number;
  executor_role_id?: number;
};

export const EMPTY_REGULAR_TASK_TEMPLATE_LIST_FILTERS: RegularTaskTemplateListFilters = {};

export const LEGACY_ORG_SCOPE_URL_PARAMS = [ORG_GROUP_ID_PARAM, ORG_UNIT_ID_PARAM] as const;

export function hasActiveRegularTaskTemplateListFilters(
  filters: RegularTaskTemplateListFilters,
): boolean {
  return (
    filters.org_group_id != null ||
    filters.org_unit_id != null ||
    filters.executor_role_id != null
  );
}

export function buildRegularTasksListApiQuery(
  filters: RegularTaskTemplateListFilters,
  base: {
    status: "all" | "active" | "inactive";
    limit: number;
    offset: number;
  },
): Record<string, string | number | undefined> {
  return {
    status: base.status,
    limit: base.limit,
    offset: base.offset,
    org_group_id: filters.org_group_id ?? undefined,
    org_unit_id: filters.org_unit_id ?? undefined,
    executor_role_id: filters.executor_role_id ?? undefined,
  };
}

export function resetRegularTaskTemplateListFilters(): RegularTaskTemplateListFilters {
  return {};
}

export function deriveExecutorRoleOptionsFromTemplates(
  templates: readonly TemplateExecutorRoleSource[],
): TemplateFormExecutorRoleOption[] {
  const byId = new Map<number, TemplateFormExecutorRoleOption>();

  for (const template of templates) {
    const roleId = Number(template.executor_role_id);
    if (!Number.isFinite(roleId) || roleId <= 0 || byId.has(roleId)) continue;

    const name = String(template.executor_role_name ?? "").trim() || null;
    const code = String(template.executor_role_code ?? "").trim() || null;
    byId.set(roleId, { role_id: roleId, name, code });
  }

  return [...byId.values()].sort((a, b) => {
    const left = String(a.name ?? a.code ?? `#${a.role_id}`);
    const right = String(b.name ?? b.code ?? `#${b.role_id}`);
    return left.localeCompare(right, "ru");
  });
}

export function isExecutorRoleAllowedForOptions(
  roleId: number | undefined,
  options: readonly TemplateFormExecutorRoleOption[],
): boolean {
  if (roleId == null) return true;
  return options.some((option) => option.role_id === roleId);
}

export function stripExecutorRoleFilter(
  filters: RegularTaskTemplateListFilters,
): RegularTaskTemplateListFilters {
  const next: RegularTaskTemplateListFilters = { ...filters };
  delete next.executor_role_id;
  return next;
}

export function clearExecutorRoleIfNotAllowed(
  filters: RegularTaskTemplateListFilters,
  options: readonly TemplateFormExecutorRoleOption[],
): RegularTaskTemplateListFilters {
  if (isExecutorRoleAllowedForOptions(filters.executor_role_id, options)) {
    return filters;
  }
  return applyExecutorRoleFilterChange(filters, null);
}

export function applyGroupFilterChange(
  filters: RegularTaskTemplateListFilters,
  nextGroupId: number | null,
  orgUnitOptions: readonly OrgUnitSelectOption[],
  executorRoleOptions: readonly TemplateFormExecutorRoleOption[] = [],
): RegularTaskTemplateListFilters {
  const next: RegularTaskTemplateListFilters = { ...filters };

  if (nextGroupId == null) {
    delete next.org_group_id;
    delete next.org_unit_id;
    return clearExecutorRoleIfNotAllowed(next, executorRoleOptions);
  }

  next.org_group_id = nextGroupId;
  if (!isOrgUnitAllowedForGroup(next.org_unit_id, nextGroupId, orgUnitOptions)) {
    delete next.org_unit_id;
  }
  return clearExecutorRoleIfNotAllowed(next, executorRoleOptions);
}

export function applyUnitFilterChange(
  filters: RegularTaskTemplateListFilters,
  nextUnitId: number | null,
  executorRoleOptions: readonly TemplateFormExecutorRoleOption[] = [],
): RegularTaskTemplateListFilters {
  const next: RegularTaskTemplateListFilters = { ...filters };
  if (nextUnitId == null) {
    delete next.org_unit_id;
    return clearExecutorRoleIfNotAllowed(next, executorRoleOptions);
  }
  next.org_unit_id = nextUnitId;
  return clearExecutorRoleIfNotAllowed(next, executorRoleOptions);
}

export function applyExecutorRoleFilterChange(
  filters: RegularTaskTemplateListFilters,
  nextRoleId: number | null,
): RegularTaskTemplateListFilters {
  const next: RegularTaskTemplateListFilters = { ...filters };
  if (nextRoleId == null) {
    delete next.executor_role_id;
    return next;
  }
  next.executor_role_id = nextRoleId;
  return next;
}

export function filterTemplateListOrgUnits(
  options: readonly OrgUnitSelectOption[],
  orgGroupId: number | undefined,
): OrgUnitSelectOption[] {
  return filterOrgUnitOptionsForGroup(options, orgGroupId);
}

export function stripLegacyOrgScopeParams(params: URLSearchParams): boolean {
  let changed = false;
  for (const key of LEGACY_ORG_SCOPE_URL_PARAMS) {
    if (!params.has(key)) continue;
    params.delete(key);
    changed = true;
  }
  return changed;
}
