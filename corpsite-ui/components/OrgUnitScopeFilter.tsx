// FILE: corpsite-ui/components/OrgUnitScopeFilter.tsx
"use client";

import * as React from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { isOrgUnitAllowedForGroup } from "@/lib/taskOrgFilters";
import {
  ORG_UNIT_ID_PARAM,
  readOrgScopeFromSearchParams,
} from "@/lib/orgScope";
import type { OrgUnitSelectOption } from "@/lib/orgUnitsSelect";
import { useOrgUnitScopeOptions } from "@/lib/useOrgUnitScopeOptions";

type OrgUnitScopeFilterProps = {
  basePath: string;
  className?: string;
  label?: string;
  allLabel?: string;
  disabled?: boolean;
  resetParamsOnChange?: string[];
  /** Controlled mode: org group driving the unit list (instead of URL). */
  orgGroupId?: number | null;
  value?: number | null;
  onChange?: (unitId: number | null) => void;
  /** Optional injected options (e.g. shared hook in PersonnelOrderItemEditor). */
  unitOptions?: OrgUnitSelectOption[];
  /** Full catalog for selection validation (defaults to unitOptions / internal catalog). */
  catalogUnitOptions?: OrgUnitSelectOption[];
  unitsLoading?: boolean;
  unitsError?: string | null;
};

export default function OrgUnitScopeFilter({
  basePath,
  className,
  label = "Отделение",
  allLabel = "Все отделения",
  disabled = false,
  resetParamsOnChange = ["offset"],
  orgGroupId: controlledOrgGroupId,
  value,
  onChange,
  unitOptions: injectedUnitOptions,
  catalogUnitOptions: injectedCatalogUnitOptions,
  unitsLoading: injectedUnitsLoading,
  unitsError: injectedUnitsError,
}: OrgUnitScopeFilterProps) {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();

  const isControlled = onChange != null;

  const orgScope = React.useMemo(() => readOrgScopeFromSearchParams(sp), [sp]);
  const orgGroupId = isControlled ? (controlledOrgGroupId ?? null) : orgScope.org_group_id;
  const selectedOrgUnitId = isControlled ? (value ?? null) : orgScope.org_unit_id;

  const internal = useOrgUnitScopeOptions(orgGroupId, injectedUnitOptions == null);
  const options = injectedUnitOptions ?? internal.options;
  const catalogOptions = injectedCatalogUnitOptions ?? injectedUnitOptions ?? internal.catalogOptions;
  const loading = injectedUnitsLoading ?? internal.loading;
  const error = injectedUnitsError ?? internal.error;

  React.useEffect(() => {
    if (!isControlled || selectedOrgUnitId == null) return;
    if (catalogOptions.length === 0) return;
    const allowed = isOrgUnitAllowedForGroup(
      selectedOrgUnitId,
      orgGroupId ?? undefined,
      catalogOptions,
    );
    if (!allowed) onChange?.(null);
  }, [isControlled, selectedOrgUnitId, orgGroupId, catalogOptions, onChange]);

  function handleChange(nextValue: string) {
    const parsed = nextValue ? Number(nextValue) : null;
    const unitId =
      parsed != null && Number.isFinite(parsed) && parsed > 0 ? Math.trunc(parsed) : null;

    if (isControlled) {
      onChange?.(unitId);
      return;
    }

    const targetPath = (pathname || "").trim() || basePath;
    const params = new URLSearchParams(sp.toString());

    if (!nextValue) {
      params.delete(ORG_UNIT_ID_PARAM);
      params.delete("org_unit_name");
    } else {
      params.set(ORG_UNIT_ID_PARAM, nextValue);
      const picked = options.find((row) => String(row.unit_id) === nextValue);
      if (picked) {
        params.set("org_unit_name", picked.name.replace(/^—\s*/g, "").trim());
      } else {
        params.delete("org_unit_name");
      }
    }

    for (const key of resetParamsOnChange) {
      const normalized = String(key || "").trim();
      if (!normalized) continue;
      params.delete(normalized);
    }

    const query = params.toString();
    router.replace(query ? `${targetPath}?${query}` : targetPath);
  }

  return (
    <div className={className} data-testid="org-unit-scope-filter">
      <label className="mb-1 block text-sm font-medium text-zinc-800 dark:text-zinc-200">{label}</label>
      <select
        data-testid="org-unit-scope-filter-select"
        value={selectedOrgUnitId != null ? String(selectedOrgUnitId) : ""}
        onChange={(e) => handleChange(e.target.value)}
        disabled={disabled || loading}
        className="w-full rounded-md border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none disabled:opacity-60"
      >
        <option value="">{allLabel}</option>
        {options.map((row) => (
          <option key={row.unit_id} value={String(row.unit_id)}>
            {row.name}
          </option>
        ))}
      </select>
      {loading ? <div className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">Загрузка…</div> : null}
      {error ? <div className="mt-1 text-xs text-red-600 dark:text-red-400">{error}</div> : null}
    </div>
  );
}
