"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { apiAuthMe } from "@/lib/api";
import type { MeInfo } from "@/lib/types";
import TaskOrgFiltersBar from "@/components/TaskOrgFiltersBar";
import { readTaskOrgFiltersFromSearchParams } from "@/lib/taskOrgFilters";

import {
  listDocuments,
  listWorkspaces,
  mapOoApiError,
  OO_BASE_PATH,
} from "../_lib/api";
import type { DocumentSummary, WorkspaceSummary } from "../_lib/types";
import { WORKSPACE_STAGE_FILTER_OPTIONS, DOCUMENT_STATUS_FILTER_OPTIONS } from "../_lib/status";
import { canSeeOperationalOrdersNav } from "../_lib/permissions";
import WorkspacesTable from "./WorkspacesTable";
import DocumentsTable from "./DocumentsTable";
import AccessDeniedPanel from "./AccessDeniedPanel";

type TabKey = "workspaces" | "documents";

function parseTab(value: string | null): TabKey {
  return value === "documents" ? "documents" : "workspaces";
}

export default function OperationalOrdersPageClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const tab = parseTab(searchParams.get("tab"));
  const orgFilters = React.useMemo(() => readTaskOrgFiltersFromSearchParams(searchParams), [searchParams]);

  const [me, setMe] = React.useState<MeInfo | null>(null);
  const [workspaces, setWorkspaces] = React.useState<WorkspaceSummary[]>([]);
  const [documents, setDocuments] = React.useState<DocumentSummary[]>([]);
  const [total, setTotal] = React.useState(0);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const stage = searchParams.get("stage") || "";
  const docStatus = searchParams.get("doc_status") || "";
  const scope = searchParams.get("scope") || "all";
  const promoted = searchParams.get("promoted") || "";
  const lang = searchParams.get("lang") || "";

  React.useEffect(() => {
    apiAuthMe().then(setMe).catch(() => setMe(null));
  }, []);

  const load = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (tab === "documents") {
        const res = await listDocuments({
          status: docStatus || undefined,
          submitting_org_unit_id: orgFilters.org_unit_id ?? undefined,
          limit: 100,
          offset: 0,
        });
        setDocuments(res.items);
        setTotal(res.total);
        setWorkspaces([]);
      } else {
        const res = await listWorkspaces({
          stage: stage || undefined,
          submitting_org_unit_id: orgFilters.org_unit_id ?? undefined,
          record_creator_user_id: scope === "mine" && me?.user_id ? me.user_id : undefined,
          promoted: promoted === "yes" ? true : promoted === "no" ? false : undefined,
          limit: 100,
          offset: 0,
        });
        let items = res.items;
        if (lang === "ru") items = items.filter((w) => w.ru_present);
        if (lang === "kk") items = items.filter((w) => w.kk_present);
        if (lang === "both") items = items.filter((w) => w.ru_present && w.kk_present);
        setWorkspaces(items);
        setTotal(res.total);
        setDocuments([]);
      }
    } catch (e) {
      setWorkspaces([]);
      setDocuments([]);
      setTotal(0);
      setError(mapOoApiError(e, "Не удалось загрузить данные"));
    } finally {
      setLoading(false);
    }
  }, [tab, stage, docStatus, scope, promoted, lang, orgFilters.org_unit_id, me?.user_id]);

  React.useEffect(() => {
    void load();
  }, [load]);

  function updateParams(patch: Record<string, string | null>) {
    const params = new URLSearchParams(searchParams.toString());
    for (const [key, value] of Object.entries(patch)) {
      if (!value) params.delete(key);
      else params.set(key, value);
    }
    router.replace(`${OO_BASE_PATH}?${params.toString()}`);
  }

  if (me && !canSeeOperationalOrdersNav(me)) {
    return <AccessDeniedPanel me={me} />;
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className={`rounded-lg px-3 py-1.5 text-sm font-medium ${tab === "workspaces" ? "bg-blue-600 text-white" : "bg-zinc-100 dark:bg-zinc-900"}`}
          onClick={() => updateParams({ tab: "workspaces" })}
        >
          Рабочие проекты
        </button>
        <button
          type="button"
          className={`rounded-lg px-3 py-1.5 text-sm font-medium ${tab === "documents" ? "bg-blue-600 text-white" : "bg-zinc-100 dark:bg-zinc-900"}`}
          onClick={() => updateParams({ tab: "documents" })}
        >
          Официальные документы
        </button>
      </div>

      <TaskOrgFiltersBar basePath={OO_BASE_PATH} />

      {tab === "workspaces" ? (
        <div className="flex flex-wrap gap-3 text-sm">
          <label className="flex items-center gap-2">
            Стадия
            <select
              className="rounded-md border px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900"
              value={stage}
              onChange={(e) => updateParams({ stage: e.target.value || null })}
            >
              <option value="">Все</option>
              {WORKSPACE_STAGE_FILTER_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2">
            Охват
            <select
              className="rounded-md border px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900"
              value={scope}
              onChange={(e) => updateParams({ scope: e.target.value === "mine" ? "mine" : null })}
            >
              <option value="all">Доступные</option>
              <option value="mine">Созданные мной</option>
            </select>
          </label>
          <label className="flex items-center gap-2">
            Промotion
            <select
              className="rounded-md border px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900"
              value={promoted}
              onChange={(e) => updateParams({ promoted: e.target.value || null })}
            >
              <option value="">Все</option>
              <option value="yes">Promoted</option>
              <option value="no">Не promoted</option>
            </select>
          </label>
          <label className="flex items-center gap-2">
            Языки
            <select
              className="rounded-md border px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900"
              value={lang}
              onChange={(e) => updateParams({ lang: e.target.value || null })}
            >
              <option value="">Все</option>
              <option value="ru">RU</option>
              <option value="kk">KK</option>
              <option value="both">RU+KK</option>
            </select>
          </label>
        </div>
      ) : (
        <div className="flex flex-wrap gap-3 text-sm">
          <label className="flex items-center gap-2">
            Статус
            <select
              className="rounded-md border px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900"
              value={docStatus}
              onChange={(e) => updateParams({ doc_status: e.target.value || null })}
            >
              <option value="">Все</option>
              {DOCUMENT_STATUS_FILTER_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
        </div>
      )}

      {error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>
      ) : null}

      {tab === "workspaces" ? (
        <>
          <p className="text-xs text-zinc-500">Всего: {total}</p>
          <WorkspacesTable items={workspaces} loading={loading} />
        </>
      ) : (
        <>
          <p className="text-xs text-zinc-500">Всего: {total}</p>
          <DocumentsTable items={documents} loading={loading} />
        </>
      )}
    </div>
  );
}
