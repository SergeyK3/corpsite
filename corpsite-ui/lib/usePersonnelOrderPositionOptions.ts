"use client";

import * as React from "react";

import {
  buildPersonnelOrderPositionSelectGroups,
  flattenPersonnelOrderPositionGroups,
  loadGlobalPositionCatalogCached,
  loadScopedPositionOptions,
  type PersonnelOrderPositionSelectGroup,
  type TaskOrgFilterOption,
} from "./taskOrgFilters";

type UsePersonnelOrderPositionOptionsArgs = {
  enabled: boolean;
  orgUnitId: number | null;
  orgGroupId: number | null;
};

type UsePersonnelOrderPositionOptionsResult = {
  positionGroups: PersonnelOrderPositionSelectGroup[];
  allOptions: TaskOrgFilterOption[];
  scopedOptions: TaskOrgFilterOption[];
  globalOptions: TaskOrgFilterOption[];
  loading: boolean;
};

export function usePersonnelOrderPositionOptions({
  enabled,
  orgUnitId,
  orgGroupId,
}: UsePersonnelOrderPositionOptionsArgs): UsePersonnelOrderPositionOptionsResult {
  const [globalOptions, setGlobalOptions] = React.useState<TaskOrgFilterOption[]>([]);
  const [globalLoading, setGlobalLoading] = React.useState(false);
  const [scopedOptions, setScopedOptions] = React.useState<TaskOrgFilterOption[]>([]);
  const [scopedLoading, setScopedLoading] = React.useState(false);

  React.useEffect(() => {
    if (!enabled) {
      setGlobalOptions([]);
      setGlobalLoading(false);
      return;
    }

    let cancelled = false;
    setGlobalLoading(true);

    void loadGlobalPositionCatalogCached()
      .then((options) => {
        if (!cancelled) setGlobalOptions(options);
      })
      .catch(() => {
        if (!cancelled) setGlobalOptions([]);
      })
      .finally(() => {
        if (!cancelled) setGlobalLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [enabled]);

  React.useEffect(() => {
    if (!enabled || orgUnitId == null) {
      setScopedOptions([]);
      setScopedLoading(false);
      return;
    }

    let cancelled = false;
    setScopedLoading(true);

    void loadScopedPositionOptions({
      org_group_id: orgGroupId ?? undefined,
      org_unit_id: orgUnitId,
    })
      .then((options) => {
        if (!cancelled) setScopedOptions(options);
      })
      .catch(() => {
        if (!cancelled) setScopedOptions([]);
      })
      .finally(() => {
        if (!cancelled) setScopedLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [enabled, orgGroupId, orgUnitId]);

  const positionGroups = React.useMemo(
    () => buildPersonnelOrderPositionSelectGroups(scopedOptions, globalOptions),
    [scopedOptions, globalOptions],
  );

  const allOptions = React.useMemo(
    () => flattenPersonnelOrderPositionGroups(positionGroups),
    [positionGroups],
  );

  return {
    positionGroups,
    allOptions,
    scopedOptions,
    globalOptions,
    loading: globalLoading || scopedLoading,
  };
}
