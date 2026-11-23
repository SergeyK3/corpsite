"use client";

import * as React from "react";

import {
  buildAllowedPositionSelectGroups,
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
  /** When true, skip global catalog and expose only scope=allowed positions for the unit. */
  allowedOnly?: boolean;
  reloadKey?: number;
};

type UsePersonnelOrderPositionOptionsResult = {
  positionGroups: PersonnelOrderPositionSelectGroup[];
  allOptions: TaskOrgFilterOption[];
  scopedOptions: TaskOrgFilterOption[];
  globalOptions: TaskOrgFilterOption[];
  loading: boolean;
  error: string | null;
};

const EMPTY_OPTIONS: TaskOrgFilterOption[] = [];

export function usePersonnelOrderPositionOptions({
  enabled,
  orgUnitId,
  orgGroupId,
  allowedOnly = false,
  reloadKey = 0,
}: UsePersonnelOrderPositionOptionsArgs): UsePersonnelOrderPositionOptionsResult {
  const [globalOptions, setGlobalOptions] = React.useState<TaskOrgFilterOption[]>([]);
  const [globalLoading, setGlobalLoading] = React.useState(false);
  const [scopedOptions, setScopedOptions] = React.useState<TaskOrgFilterOption[]>([]);
  const [scopedLoading, setScopedLoading] = React.useState(false);
  const [scopedRequestKey, setScopedRequestKey] = React.useState<string | null>(null);
  const [scopedError, setScopedError] = React.useState<string | null>(null);
  const requestKey = enabled && orgUnitId != null ? `${orgUnitId}:${reloadKey}` : null;

  React.useEffect(() => {
    if (!enabled || allowedOnly) {
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
  }, [enabled, allowedOnly]);

  React.useEffect(() => {
    if (!enabled || orgUnitId == null) {
      setScopedOptions([]);
      setScopedLoading(false);
      setScopedRequestKey(null);
      setScopedError(null);
      return;
    }

    let cancelled = false;
    setScopedLoading(true);
    setScopedOptions([]);
    setScopedRequestKey(null);
    setScopedError(null);

    void loadScopedPositionOptions({
      org_unit_id: orgUnitId,
      scope: "allowed",
      ...(orgUnitId == null && orgGroupId != null ? { org_group_id: orgGroupId } : {}),
    })
      .then((options) => {
        if (!cancelled) {
          setScopedOptions(options);
          setScopedRequestKey(requestKey);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setScopedOptions([]);
          setScopedRequestKey(requestKey);
          setScopedError("Не удалось загрузить должности для отделения. Нажмите «Повторить загрузку должностей».");
        }
      })
      .finally(() => {
        if (!cancelled) setScopedLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [enabled, orgGroupId, orgUnitId, reloadKey]);

  const currentScopedOptions = requestKey != null && scopedRequestKey === requestKey ? scopedOptions : EMPTY_OPTIONS;
  const currentScopedError = requestKey != null && scopedRequestKey === requestKey ? scopedError : null;

  const positionGroups = React.useMemo(
    () =>
      allowedOnly
        ? buildAllowedPositionSelectGroups(currentScopedOptions)
        : buildPersonnelOrderPositionSelectGroups(currentScopedOptions, globalOptions),
    [allowedOnly, currentScopedOptions, globalOptions],
  );

  const allOptions = React.useMemo(
    () => flattenPersonnelOrderPositionGroups(positionGroups),
    [positionGroups],
  );

  return {
    positionGroups,
    allOptions,
    scopedOptions: currentScopedOptions,
    globalOptions,
    loading: globalLoading || scopedLoading || (requestKey != null && scopedRequestKey !== requestKey),
    error: currentScopedError,
  };
}
