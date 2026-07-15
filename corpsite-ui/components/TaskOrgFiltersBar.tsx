// FILE: corpsite-ui/components/TaskOrgFiltersBar.tsx
"use client";

import * as React from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import OrgScopeFilter from "@/components/OrgScopeFilter";
import {
  ORG_UNIT_ID_PARAM,
} from "@/lib/orgScope";
import { loadOrgUnitSelectOptions } from "@/lib/orgUnitsSelect";
import {
  buildTaskOrgFiltersResetUrl,
  filterOrgUnitOptionsForGroup,
  hasActiveTaskOrgFilters,
  isOrgUnitAllowedForGroup,
  isPositionAllowedInOptions,
  loadScopedPositionOptions,
  readTaskOrgFiltersFromSearchParams,
  TASK_ORG_FILTER_RESET_PARAM_KEYS,
  TASK_POSITION_ID_PARAM,
  type TaskOrgFilterOption,
} from "@/lib/taskOrgFilters";

type TaskOrgFiltersBarProps = {
  basePath?: string;
  visible?: boolean;
  className?: string;
};

const selectClassName =
  "h-9 min-w-[220px] max-w-full rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 text-[13px] text-zinc-900 dark:text-zinc-50 outline-none transition focus:border-zinc-400";

export default function TaskOrgFiltersBar({
  basePath = "/tasks",
  visible = true,
  className,
}: TaskOrgFiltersBarProps) {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();

  const filters = React.useMemo(() => readTaskOrgFiltersFromSearchParams(sp), [sp]);
  const orgGroupId = filters.org_group_id;
  const orgUnitId = filters.org_unit_id != null ? String(filters.org_unit_id) : "";
  const positionId = filters.position_id != null ? String(filters.position_id) : "";

  const [orgUnitOptions, setOrgUnitOptions] = React.useState<
    Array<{ unit_id: number; name: string; group_id: number | null }>
  >([]);
  const [positionOptions, setPositionOptions] = React.useState<TaskOrgFilterOption[]>([]);
  const [refsLoading, setRefsLoading] = React.useState(false);
  const [refsError, setRefsError] = React.useState<string | null>(null);

  const departmentOptions = React.useMemo(
    () => filterOrgUnitOptionsForGroup(orgUnitOptions, orgGroupId),
    [orgUnitOptions, orgGroupId],
  );

  const hasActiveFilters = hasActiveTaskOrgFilters(filters);

  React.useEffect(() => {
    if (!visible) return;
    let cancelled = false;

    (async () => {
      setRefsLoading(true);
      setRefsError(null);
      try {
        const options = await loadOrgUnitSelectOptions();
        if (cancelled) return;
        setOrgUnitOptions(options);
      } catch (e: unknown) {
        if (cancelled) return;
        setOrgUnitOptions([]);
        setRefsError(e instanceof Error ? e.message : "Не удалось загрузить отделения.");
      } finally {
        if (!cancelled) setRefsLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [visible]);

  React.useEffect(() => {
    if (!visible) return;
    let cancelled = false;

    (async () => {
      try {
        const options = await loadScopedPositionOptions({
          org_group_id: orgGroupId,
          org_unit_id: filters.org_unit_id,
          scope: "used",
        });
        if (cancelled) return;
        setPositionOptions(options);
      } catch {
        if (cancelled) return;
        setPositionOptions([]);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [visible, orgGroupId, filters.org_unit_id]);

  React.useEffect(() => {
    if (!visible) return;

    const allowedUnit = isOrgUnitAllowedForGroup(filters.org_unit_id, orgGroupId, orgUnitOptions);
    const allowedPosition = isPositionAllowedInOptions(filters.position_id, positionOptions);
    if (allowedUnit && allowedPosition) return;

    const params = new URLSearchParams(sp.toString());
    let changed = false;

    if (!allowedUnit && params.has(ORG_UNIT_ID_PARAM)) {
      params.delete(ORG_UNIT_ID_PARAM);
      changed = true;
    }
    if (!allowedPosition && params.has(TASK_POSITION_ID_PARAM)) {
      params.delete(TASK_POSITION_ID_PARAM);
      changed = true;
    }
    if (!changed) return;

    params.set("offset", "0");
    const targetPath = (pathname || "").trim() || basePath;
    router.replace(`${targetPath}?${params.toString()}`);
  }, [
    visible,
    orgGroupId,
    filters.org_unit_id,
    filters.position_id,
    orgUnitOptions,
    positionOptions,
    sp,
    pathname,
    basePath,
    router,
  ]);

  function updateFilterParam(key: string, value: string, resetKeys: string[] = []) {
    const targetPath = (pathname || "").trim() || basePath;
    const params = new URLSearchParams(sp.toString());

    if (!value) params.delete(key);
    else params.set(key, value);

    for (const resetKey of resetKeys) {
      const normalized = String(resetKey || "").trim();
      if (!normalized) continue;
      params.delete(normalized);
    }

    params.set("offset", "0");
    router.replace(`${targetPath}?${params.toString()}`);
  }

  function handleReset() {
    const targetPath = (pathname || "").trim() || basePath;
    router.replace(buildTaskOrgFiltersResetUrl(targetPath, new URLSearchParams(sp.toString())));
  }

  if (!visible) return null;

  return (
    <div
      className={["flex flex-col gap-2", className].filter(Boolean).join(" ")}
      data-testid="task-org-filters"
    >
      <div className="flex flex-wrap items-end gap-3">
        <OrgScopeFilter
          basePath={basePath}
          className="min-w-[220px] max-w-full"
          resetParamsOnChange={[...TASK_ORG_FILTER_RESET_PARAM_KEYS].filter(
            (key) => key !== "org_group_id",
          )}
        />

        <div className="min-w-[220px] max-w-full">
          <label className="mb-1 block text-sm font-medium text-zinc-800 dark:text-zinc-200">
            Отделение
          </label>
          <select
            value={orgUnitId}
            onChange={(e) =>
              updateFilterParam(ORG_UNIT_ID_PARAM, e.target.value, [TASK_POSITION_ID_PARAM])
            }
            disabled={refsLoading}
            data-testid="task-org-filter-unit"
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

        <div className="min-w-[220px] max-w-full">
          <label className="mb-1 block text-sm font-medium text-zinc-800 dark:text-zinc-200">
            Должность
          </label>
          <select
            value={positionId}
            onChange={(e) => updateFilterParam(TASK_POSITION_ID_PARAM, e.target.value)}
            data-testid="task-org-filter-position"
            className={selectClassName}
          >
            <option value="">Все</option>
            {positionOptions.map((position) => (
              <option key={position.id} value={String(position.id)}>
                {position.label}
              </option>
            ))}
          </select>
        </div>

        {hasActiveFilters ? (
          <button
            type="button"
            onClick={handleReset}
            data-testid="task-org-filter-reset"
            className="h-9 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 text-[13px] text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700"
          >
            Сбросить
          </button>
        ) : null}
      </div>

      {refsError ? <div className="text-xs text-red-600 dark:text-red-400">{refsError}</div> : null}
    </div>
  );
}
