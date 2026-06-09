// FILE: corpsite-ui/components/OrgScopeFilter.tsx
"use client";

import * as React from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import {
  fetchDepartmentGroups,
  mergeOrgScopeIntoUrl,
  ORG_GROUP_ID_PARAM,
  readOrgScopeFromSearchParams,
  type DepartmentGroupRow,
} from "@/lib/orgScope";

type OrgScopeFilterProps = {
  basePath: string;
  className?: string;
  label?: string;
  disabled?: boolean;
  resetParamsOnChange?: string[];
};

export default function OrgScopeFilter({
  basePath,
  className,
  label = "Группа отделений",
  disabled = false,
  resetParamsOnChange = ["offset"],
}: OrgScopeFilterProps) {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();

  const [groups, setGroups] = React.useState<DepartmentGroupRow[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const selectedGroupId = React.useMemo(() => {
    return readOrgScopeFromSearchParams(sp).org_group_id ?? null;
  }, [sp]);

  React.useEffect(() => {
    let cancelled = false;

    (async () => {
      setLoading(true);
      setError(null);
      try {
        const rows = await fetchDepartmentGroups();
        if (cancelled) return;
        setGroups(rows);
      } catch (e: unknown) {
        if (cancelled) return;
        setGroups([]);
        setError(e instanceof Error ? e.message : "Не удалось загрузить группы отделений.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  function handleChange(nextValue: string) {
    const targetPath = (pathname || "").trim() || basePath;
    const params = new URLSearchParams(sp.toString());

    if (!nextValue) {
      params.delete(ORG_GROUP_ID_PARAM);
    } else {
      params.set(ORG_GROUP_ID_PARAM, nextValue);
    }

    for (const key of resetParamsOnChange) {
      const normalized = String(key || "").trim();
      if (!normalized) continue;
      params.delete(normalized);
    }

    const nextUrl = mergeOrgScopeIntoUrl(targetPath, params, {});
    router.replace(nextUrl);
  }

  return (
    <div className={className}>
      <label className="mb-1 block text-sm font-medium text-zinc-800 dark:text-zinc-200">{label}</label>
      <select
        value={selectedGroupId != null ? String(selectedGroupId) : ""}
        onChange={(e) => handleChange(e.target.value)}
        disabled={disabled || loading}
        className="w-full rounded-md border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none disabled:opacity-60"
      >
        <option value="">Все</option>
        {groups.map((group) => (
          <option key={group.group_id} value={String(group.group_id)}>
            {group.group_name || `Группа ${group.group_id}`}
          </option>
        ))}
      </select>
      {loading ? <div className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">Загрузка…</div> : null}
      {error ? <div className="mt-1 text-xs text-red-600 dark:text-red-400">{error}</div> : null}
    </div>
  );
}
