"use client";

import * as React from "react";

import { loadOrgUnitSelectOptions, type OrgUnitSelectOption } from "@/lib/orgUnitsSelect";
import { filterOrgUnitOptionsForGroup, normalizeOrgGroupId } from "@/lib/taskOrgFilters";

/**
 * Org-unit options for cascade filters.
 * Matches TaskOrgFiltersBar / loadOrgUnitSelectOptions pipeline:
 * full enriched catalog (strip MMC root, inherit group_id) + client filter by group.
 */
export function useOrgUnitScopeOptions(
  orgGroupId: number | null | undefined,
  enabled = true,
) {
  const normalizedGroupId = normalizeOrgGroupId(orgGroupId);
  const [catalogOptions, setCatalogOptions] = React.useState<OrgUnitSelectOption[]>([]);
  const [loading, setLoading] = React.useState(enabled);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }

    let cancelled = false;

    (async () => {
      setLoading(true);
      setError(null);

      try {
        const options = await loadOrgUnitSelectOptions();
        if (cancelled) return;
        setCatalogOptions(options);
      } catch (e: unknown) {
        if (cancelled) return;
        setCatalogOptions([]);
        setError(e instanceof Error ? e.message : "Не удалось загрузить отделения.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [enabled]);

  const options = React.useMemo(
    () => filterOrgUnitOptionsForGroup(catalogOptions, normalizedGroupId ?? undefined),
    [catalogOptions, normalizedGroupId],
  );

  return {
    options,
    catalogOptions,
    loading,
    error,
    orgGroupId: normalizedGroupId,
  };
}
