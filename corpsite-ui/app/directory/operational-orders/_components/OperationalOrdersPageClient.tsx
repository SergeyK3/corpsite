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
import { canReviewOperationalOrderArchive, canSeeOperationalOrdersNav } from "../_lib/permissions";
import WorkspacesTable from "./WorkspacesTable";
import DocumentsTable from "./DocumentsTable";
import AccessDeniedPanel from "./AccessDeniedPanel";
import ArchiveReviewPanel from "./ArchiveReviewPanel";

type TabKey = "workspaces" | "documents" | "archive-review";

function parseTab(value: string | null): TabKey {
  if (value === "archive-review") return "archive-review";
  return value === "documents" ? "documents" : "workspaces";
}

export default function OperationalOrdersPageClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const tab = parseTab(searchParams.get("tab"));
  const orgFilters = React.useMemo(() => readTaskOrgFiltersFromSearchParams(searchParams), [searchParams]);

  const [me, setMe] = React.useState<MeInfo | null>(null);
  const [authLoaded, setAuthLoaded] = React.useState(false);
  const [workspaces, setWorkspaces] = React.useState<WorkspaceSummary[]>([]);
  const [documents, setDocuments] = React.useState<DocumentSummary[]>([]);
  const [total, setTotal] = React.useState(0);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const requestSequence = React.useRef(0);
  const canReadOfficialContours = Boolean(me?.is_privileged || me?.has_operational_orders_read);
  const canReviewArchive = canReviewOperationalOrderArchive(me);

  const stage = searchParams.get("stage") || "";
  const docStatus = searchParams.get("doc_status") || "";
  const scope = searchParams.get("scope") || "all";
  const promoted = searchParams.get("promoted") || "";
  const lang = searchParams.get("lang") || "";

  React.useEffect(() => {
    apiAuthMe()
      .then(setMe)
      .catch(() => setMe(null))
      .finally(() => setAuthLoaded(true));
  }, []);

  React.useEffect(() => {
    if (authLoaded && me && !canReadOfficialContours && canReviewArchive && tab !== "archive-review") {
      router.replace(`${OO_BASE_PATH}?tab=archive-review`);
    }
  }, [authLoaded, canReadOfficialContours, canReviewArchive, me, router, tab]);

  const load = React.useCallback(async () => {
    if (!authLoaded) return;
    if (tab !== "archive-review" && !canReadOfficialContours) return;
    if (tab === "archive-review" && !canReadOfficialContours && !canReviewArchive) return;
    const requestId = ++requestSequence.current;
    const isCurrent = () => requestId === requestSequence.current;
    setLoading(true);
    setError(null);
    try {
      if (tab === "archive-review") {
        if (!isCurrent()) return;
        setWorkspaces([]);
        setDocuments([]);
        setTotal(0);
      } else if (tab === "documents") {
        const res = await listDocuments({
          status: docStatus || undefined,
          submitting_org_unit_id: orgFilters.org_unit_id ?? undefined,
          limit: 100,
          offset: 0,
        });
        if (!isCurrent()) return;
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
        if (!isCurrent()) return;
        let items = res.items;
        if (lang === "ru") items = items.filter((w) => w.ru_present);
        if (lang === "kk") items = items.filter((w) => w.kk_present);
        if (lang === "both") items = items.filter((w) => w.ru_present && w.kk_present);
        setWorkspaces(items);
        setTotal(res.total);
        setDocuments([]);
      }
    } catch (e) {
      if (!isCurrent()) return;
      setWorkspaces([]);
      setDocuments([]);
      setTotal(0);
      setError(mapOoApiError(e, "Не удалось загрузить данные"));
    } finally {
      if (isCurrent()) setLoading(false);
    }
  }, [authLoaded, canReadOfficialContours, canReviewArchive, tab, stage, docStatus, scope, promoted, lang, orgFilters.org_unit_id, me?.user_id]);

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

  if (!authLoaded) {
    return <p className="text-sm text-zinc-500" data-testid="operational-orders-access-loading">Проверка доступа…</p>;
  }

  if (!me || !canSeeOperationalOrdersNav(me)) {
    return <AccessDeniedPanel me={me} />;
  }

  if (me && !canReadOfficialContours && canReviewArchive && tab !== "archive-review") {
    return <p className="text-sm text-zinc-500">Открываем архив на проверке…</p>;
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Разделы производственных приказов">
        {canReadOfficialContours ? (
          <>
            <button
              type="button"
              role="tab"
              aria-selected={tab === "workspaces"}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium ${tab === "workspaces" ? "bg-blue-600 text-white" : "bg-zinc-100 dark:bg-zinc-900"}`}
              onClick={() => updateParams({ tab: "workspaces" })}
            >
              Рабочие проекты
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={tab === "documents"}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium ${tab === "documents" ? "bg-blue-600 text-white" : "bg-zinc-100 dark:bg-zinc-900"}`}
              onClick={() => updateParams({ tab: "documents" })}
            >
              Официальные документы
            </button>
          </>
        ) : null}
        <button
          type="button"
          role="tab"
          aria-selected={tab === "archive-review"}
          className={`rounded-lg px-3 py-1.5 text-sm font-medium ${tab === "archive-review" ? "bg-blue-600 text-white" : "bg-zinc-100 dark:bg-zinc-900"}`}
          onClick={() => updateParams({ tab: "archive-review" })}
        >
          Архив на проверке
        </button>
      </div>

      {tab !== "archive-review" ? <TaskOrgFiltersBar basePath={OO_BASE_PATH} /> : null}

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
      ) : tab === "documents" ? (
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
      ) : null}

      {error && tab !== "archive-review" ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>
      ) : null}

      {tab === "archive-review" ? (
        <ArchiveReviewPanel
          canReview={canReviewArchive}
          reviewerName={me.full_name?.trim() || me.login?.trim() || "Текущий пользователь"}
        />
      ) : tab === "workspaces" ? (
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
