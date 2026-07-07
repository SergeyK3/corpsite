// FILE: corpsite-ui/components/RegularTaskTemplateFiltersBar.tsx
"use client";

import * as React from "react";

import {
  applyExecutorRoleFilterChange,
  applyGroupFilterChange,
  applyUnitFilterChange,
  filterTemplateListOrgUnits,
  hasActiveRegularTaskTemplateListFilters,
  resetRegularTaskTemplateListFilters,
  type RegularTaskTemplateListFilters,
} from "@/lib/regularTaskTemplateListFilters";
import { fetchDepartmentGroups, type DepartmentGroupRow } from "@/lib/orgScope";
import { loadOrgUnitSelectOptions } from "@/lib/orgUnitsSelect";
import type { TemplateFormExecutorRoleOption } from "@/app/regular-tasks/_components/TemplateForm";

type RegularTaskTemplateFiltersBarProps = {
  filters: RegularTaskTemplateListFilters;
  onChange: (next: RegularTaskTemplateListFilters) => void;
  executorRoleOptions: TemplateFormExecutorRoleOption[];
  executorRolesLoading?: boolean;
  className?: string;
};

const selectClassName =
  "w-full rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white/60 dark:bg-zinc-900/60 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition focus:border-zinc-500";

function executorRoleLabel(role: TemplateFormExecutorRoleOption): string {
  const name = String(role.name ?? "").trim();
  if (name) return name;
  const code = String(role.code ?? "").trim();
  if (code) return code;
  return `#${role.role_id}`;
}

export default function RegularTaskTemplateFiltersBar({
  filters,
  onChange,
  executorRoleOptions,
  executorRolesLoading = false,
  className,
}: RegularTaskTemplateFiltersBarProps) {
  const [groups, setGroups] = React.useState<DepartmentGroupRow[]>([]);
  const [groupsLoading, setGroupsLoading] = React.useState(true);
  const [groupsError, setGroupsError] = React.useState<string | null>(null);

  const [orgUnitOptions, setOrgUnitOptions] = React.useState<
    Array<{ unit_id: number; name: string; group_id: number | null }>
  >([]);
  const [unitsLoading, setUnitsLoading] = React.useState(true);
  const [unitsError, setUnitsError] = React.useState<string | null>(null);

  const orgGroupId = filters.org_group_id;
  const orgUnitId = filters.org_unit_id != null ? String(filters.org_unit_id) : "";
  const executorRoleId =
    filters.executor_role_id != null ? String(filters.executor_role_id) : "";

  const departmentOptions = React.useMemo(
    () => filterTemplateListOrgUnits(orgUnitOptions, orgGroupId),
    [orgUnitOptions, orgGroupId],
  );

  const hasActiveFilters = hasActiveRegularTaskTemplateListFilters(filters);

  React.useEffect(() => {
    let cancelled = false;

    (async () => {
      setGroupsLoading(true);
      setGroupsError(null);
      try {
        const rows = await fetchDepartmentGroups();
        if (cancelled) return;
        setGroups(rows);
      } catch (e: unknown) {
        if (cancelled) return;
        setGroups([]);
        setGroupsError(e instanceof Error ? e.message : "Не удалось загрузить группы отделений.");
      } finally {
        if (!cancelled) setGroupsLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  React.useEffect(() => {
    let cancelled = false;

    (async () => {
      setUnitsLoading(true);
      setUnitsError(null);
      try {
        const options = await loadOrgUnitSelectOptions();
        if (cancelled) return;
        setOrgUnitOptions(options);
      } catch (e: unknown) {
        if (cancelled) return;
        setOrgUnitOptions([]);
        setUnitsError(e instanceof Error ? e.message : "Не удалось загрузить отделения.");
      } finally {
        if (!cancelled) setUnitsLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  function handleGroupChange(value: string) {
    const parsed = value ? Number(value) : null;
    const groupId =
      parsed != null && Number.isFinite(parsed) && parsed > 0 ? Math.trunc(parsed) : null;
    onChange(applyGroupFilterChange(filters, groupId, orgUnitOptions, executorRoleOptions));
  }

  function handleUnitChange(value: string) {
    const parsed = value ? Number(value) : null;
    const unitId =
      parsed != null && Number.isFinite(parsed) && parsed > 0 ? Math.trunc(parsed) : null;
    onChange(applyUnitFilterChange(filters, unitId, executorRoleOptions));
  }

  function handleRoleChange(value: string) {
    const parsed = value ? Number(value) : null;
    const roleId =
      parsed != null && Number.isFinite(parsed) && parsed > 0 ? Math.trunc(parsed) : null;
    onChange(applyExecutorRoleFilterChange(filters, roleId));
  }

  function handleReset() {
    onChange(resetRegularTaskTemplateListFilters());
  }

  return (
    <div
      className={["flex flex-col gap-2", className].filter(Boolean).join(" ")}
      data-testid="regular-task-template-filters"
    >
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-[220px] max-w-full flex-1">
          <label className="mb-1 block text-sm font-medium text-zinc-800 dark:text-zinc-200">
            Группа отделений
          </label>
          <select
            value={orgGroupId != null ? String(orgGroupId) : ""}
            onChange={(e) => handleGroupChange(e.target.value)}
            disabled={groupsLoading}
            data-testid="regular-task-template-filter-group"
            className={selectClassName}
          >
            <option value="">Все</option>
            {groups.map((group) => (
              <option key={group.group_id} value={String(group.group_id)}>
                {group.group_name || `Группа ${group.group_id}`}
              </option>
            ))}
          </select>
        </div>

        <div className="min-w-[220px] max-w-full flex-1">
          <label className="mb-1 block text-sm font-medium text-zinc-800 dark:text-zinc-200">
            Отделение
          </label>
          <select
            value={orgUnitId}
            onChange={(e) => handleUnitChange(e.target.value)}
            disabled={unitsLoading}
            data-testid="regular-task-template-filter-unit"
            className={selectClassName}
          >
            <option value="">Все</option>
            {departmentOptions.map((unit) => (
              <option key={unit.unit_id} value={String(unit.unit_id)}>
                {unit.name}
              </option>
            ))}
          </select>
        </div>

        <div className="min-w-[220px] max-w-full flex-1">
          <label className="mb-1 block text-sm font-medium text-zinc-800 dark:text-zinc-200">
            Должность / роль исполнителя
          </label>
          <select
            value={executorRoleId}
            onChange={(e) => handleRoleChange(e.target.value)}
            disabled={executorRolesLoading}
            data-testid="regular-task-template-filter-role"
            className={selectClassName}
          >
            <option value="">Все</option>
            {executorRoleOptions.map((role) => (
              <option key={role.role_id} value={String(role.role_id)}>
                {executorRoleLabel(role)}
              </option>
            ))}
          </select>
        </div>

        {hasActiveFilters ? (
          <button
            type="button"
            onClick={handleReset}
            data-testid="regular-task-template-filter-reset"
            className="h-[42px] rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white/60 dark:bg-zinc-900/60 px-4 text-sm font-medium text-zinc-900 dark:text-zinc-50 transition hover:bg-zinc-200 dark:hover:bg-zinc-700"
          >
            Сбросить фильтры
          </button>
        ) : null}
      </div>

      {groupsError ? <div className="text-xs text-red-600 dark:text-red-400">{groupsError}</div> : null}
      {unitsError ? <div className="text-xs text-red-600 dark:text-red-400">{unitsError}</div> : null}
    </div>
  );
}
