// FILE: corpsite-ui/components/OrgUnitScopeFilter.tsx
"use client";

import * as React from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { getOrgUnitsTree } from "@/app/directory/org-units/_lib/api.client";
import { flattenOrgUnits } from "@/lib/orgUnitsTree";
import {
  ORG_UNIT_ID_PARAM,
  readOrgScopeFromSearchParams,
} from "@/lib/orgScope";

type OrgUnitScopeFilterProps = {
  basePath: string;
  className?: string;
  label?: string;
  allLabel?: string;
  disabled?: boolean;
  resetParamsOnChange?: string[];
};

export default function OrgUnitScopeFilter({
  basePath,
  className,
  label = "Отделение",
  allLabel = "Все отделения",
  disabled = false,
  resetParamsOnChange = ["offset"],
}: OrgUnitScopeFilterProps) {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();

  const orgScope = React.useMemo(() => readOrgScopeFromSearchParams(sp), [sp]);
  const orgGroupId = orgScope.org_group_id;
  const selectedOrgUnitId = orgScope.org_unit_id;

  const [options, setOptions] = React.useState<Array<{ id: number; label: string }>>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;

    (async () => {
      setLoading(true);
      setError(null);

      try {
        const tree = await getOrgUnitsTree({
          org_group_id: orgGroupId ?? undefined,
        });
        if (cancelled) return;

        const seen = new Set<number>();
        const rows = flattenOrgUnits(tree.items ?? []).filter((row) => {
          if (seen.has(row.id)) return false;
          seen.add(row.id);
          return true;
        });

        setOptions(rows);
      } catch (e: unknown) {
        if (cancelled) return;
        setOptions([]);
        setError(e instanceof Error ? e.message : "Не удалось загрузить отделения.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [orgGroupId]);

  function handleChange(nextValue: string) {
    const targetPath = (pathname || "").trim() || basePath;
    const params = new URLSearchParams(sp.toString());

    if (!nextValue) {
      params.delete(ORG_UNIT_ID_PARAM);
      params.delete("org_unit_name");
    } else {
      params.set(ORG_UNIT_ID_PARAM, nextValue);
      const picked = options.find((row) => String(row.id) === nextValue);
      if (picked) {
        params.set("org_unit_name", picked.label.replace(/^—\s*/g, "").trim());
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
    <div className={className}>
      <label className="mb-1 block text-sm font-medium text-zinc-800 dark:text-zinc-200">{label}</label>
      <select
        value={selectedOrgUnitId != null ? String(selectedOrgUnitId) : ""}
        onChange={(e) => handleChange(e.target.value)}
        disabled={disabled || loading}
        className="w-full rounded-md border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none disabled:opacity-60"
      >
        <option value="">{allLabel}</option>
        {options.map((row) => (
          <option key={row.id} value={String(row.id)}>
            {row.label}
          </option>
        ))}
      </select>
      {loading ? <div className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">Загрузка…</div> : null}
      {error ? <div className="mt-1 text-xs text-red-600 dark:text-red-400">{error}</div> : null}
    </div>
  );
}
