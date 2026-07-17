"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";

import TaskOrgFiltersBar from "@/components/TaskOrgFiltersBar";
import {
  buildPersonnelApplicationsJournalHref,
  buildPersonnelApplicationsListLoadKey,
  JOURNAL_VIEW_ARCHIVE,
  JOURNAL_VIEW_ACTIVE,
  DEFAULT_JOURNAL_SORT,
  parsePersonnelApplicationsJournalState,
  type PersonnelApplicationsWorkplace,
  workplaceBasePath,
} from "../_lib/personnelApplicationsJournalNav";
import {
  listPersonnelApplications,
  mapPersonnelApplicationsApiError,
  type PersonnelApplicationListItem,
  type PersonnelApplicationRegisterResponse,
} from "../_lib/personnelApplicationsApi.client";
import {
  PERSONNEL_APPLICATION_ARCHIVE_SORT_OPTIONS,
  PERSONNEL_APPLICATION_SORT_OPTIONS,
} from "../_lib/personnelApplicationLabels";
import { PersonnelApplicationsTable } from "./PersonnelApplicationsTable";
import PersonnelApplicationDetailDrawer from "./PersonnelApplicationDetailDrawer";
import PersonnelApplicationRegisterDrawer from "./PersonnelApplicationRegisterDrawer";

const WORKPLACE_COPY: Record<
  PersonnelApplicationsWorkplace,
  { title: string; description: string; loadError: string; testId: string }
> = {
  applications: {
    title: "Кадровые обращения",
    description: "Реестр кадровых обращений по бумажным заявлениям претендентов.",
    loadError: "Не удалось загрузить журнал кадровых обращений",
    testId: "personnel-applications-page",
  },
  applicants: {
    title: "Претенденты",
    description:
      "Рабочее место HR: регистрация претендентов, выдача ссылки на заполнение личной карточки и контроль этапов до приёма на работу.",
    loadError: "Не удалось загрузить журнал претендентов",
    testId: "personnel-applicants-workplace-page",
  },
};

type Props = {
  workplace?: PersonnelApplicationsWorkplace;
};

export default function PersonnelApplicationsPageClient({ workplace = "applications" }: Props) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const copy = WORKPLACE_COPY[workplace];
  const journalBasePath = workplaceBasePath(workplace);
  const filters = React.useMemo(
    () => parsePersonnelApplicationsJournalState(searchParams),
    [searchParams],
  );
  const listLoadKey = React.useMemo(() => buildPersonnelApplicationsListLoadKey(filters), [filters]);
  const journalReturnHref = React.useMemo(
    () => buildPersonnelApplicationsJournalHref(filters, { basePath: journalBasePath }),
    [filters, journalBasePath],
  );

  const [items, setItems] = React.useState<PersonnelApplicationListItem[]>([]);
  const [total, setTotal] = React.useState(0);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [registerOpen, setRegisterOpen] = React.useState(false);
  const [searchDraft, setSearchDraft] = React.useState(filters.q);
  const [highlightedApplicationId, setHighlightedApplicationId] = React.useState<number | null>(null);
  const [toast, setToast] = React.useState<{ message: string; kind: "success" | "error" } | null>(null);

  const inFlightLoadKeyRef = React.useRef<string | null>(null);
  const selectedApplicationId = filters.application_id;
  const detailOpen = selectedApplicationId != null;
  const isArchiveView = filters.view === JOURNAL_VIEW_ARCHIVE;
  const sortOptions = isArchiveView
    ? PERSONNEL_APPLICATION_ARCHIVE_SORT_OPTIONS
    : PERSONNEL_APPLICATION_SORT_OPTIONS;

  React.useEffect(() => {
    setSearchDraft(filters.q);
  }, [filters.q]);

  React.useEffect(() => {
    if (searchParams.get("register") === "1") {
      setRegisterOpen(true);
    }
  }, [searchParams]);

  React.useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 4000);
    return () => window.clearTimeout(timer);
  }, [toast]);

  React.useEffect(() => {
    if (highlightedApplicationId == null) return;
    const timer = window.setTimeout(() => setHighlightedApplicationId(null), 6000);
    return () => window.clearTimeout(timer);
  }, [highlightedApplicationId]);

  React.useEffect(() => {
    if (highlightedApplicationId == null || loading) return;
    const row = document.querySelector(
      `[data-testid="personnel-application-row-${highlightedApplicationId}"]`,
    );
    if (row && typeof row.scrollIntoView === "function") {
      row.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }, [highlightedApplicationId, items, loading]);

  const loadList = React.useCallback(async () => {
    if (inFlightLoadKeyRef.current === listLoadKey) return;
    inFlightLoadKeyRef.current = listLoadKey;
    setLoading(true);
    setError(null);
    try {
      const body = await listPersonnelApplications({
        q: filters.q || undefined,
        view: filters.view,
        sort: filters.sort,
        limit: filters.limit,
        offset: filters.offset,
        org_group_id: filters.org_group_id,
        org_unit_id: filters.org_unit_id,
        position_id: filters.position_id,
      });
      setItems(Array.isArray(body.items) ? body.items : []);
      setTotal(Number(body.total) || 0);
    } catch (e) {
      setItems([]);
      setTotal(0);
      setError(mapPersonnelApplicationsApiError(e, copy.loadError));
    } finally {
      if (inFlightLoadKeyRef.current === listLoadKey) {
        inFlightLoadKeyRef.current = null;
      }
      setLoading(false);
    }
  }, [
    listLoadKey,
    filters.q,
    filters.view,
    filters.sort,
    filters.limit,
    filters.offset,
    filters.org_group_id,
    filters.org_unit_id,
    filters.position_id,
    copy.loadError,
  ]);

  React.useEffect(() => {
    void loadList();
  }, [loadList]);

  function replaceJournalState(next: Partial<typeof filters>) {
    const merged = { ...filters, ...next };
    const href = buildPersonnelApplicationsJournalHref(merged, { basePath: journalBasePath });
    router.replace(href);
  }

  function applySearch() {
    const normalized = searchDraft.trim();
    if (normalized === filters.q) return;
    replaceJournalState({ q: normalized, offset: 0 });
  }

  function openDetail(applicationId: number) {
    replaceJournalState({ application_id: applicationId });
  }

  function closeDetail() {
    replaceJournalState({ application_id: null });
  }

  function handleRegistered(result: PersonnelApplicationRegisterResponse) {
    setHighlightedApplicationId(result.application_id);
    replaceJournalState({ application_id: result.application_id });
    inFlightLoadKeyRef.current = null;
    void loadList();
  }

  const page = Math.floor(filters.offset / filters.limit) + 1;
  const pageCount = Math.max(1, Math.ceil(total / filters.limit));

  return (
    <div className="space-y-4 p-4" data-testid={copy.testId}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">{copy.title}</h1>
          <p className="mt-1 text-sm text-zinc-500">{copy.description}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => {
              inFlightLoadKeyRef.current = null;
              void loadList();
            }}
            className="rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700"
            data-testid="personnel-applications-refresh"
          >
            Обновить
          </button>
          <button
            type="button"
            onClick={() => setRegisterOpen(true)}
            className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
            data-testid="personnel-applications-register-button"
          >
            Зарегистрировать претендента
          </button>
        </div>
      </div>

      <TaskOrgFiltersBar
        basePath={journalBasePath}
        className="rounded-xl border border-zinc-200 p-3 dark:border-zinc-800"
      />

      <div className="flex flex-wrap gap-2" data-testid="personnel-applications-view-tabs">
        <button
          type="button"
          onClick={() =>
            replaceJournalState({
              view: JOURNAL_VIEW_ACTIVE,
              offset: 0,
              sort: DEFAULT_JOURNAL_SORT,
              application_id: null,
            })
          }
          className={[
            "rounded-lg px-3 py-2 text-sm",
            !isArchiveView
              ? "bg-blue-600 text-white"
              : "border border-zinc-300 text-zinc-700 dark:border-zinc-700 dark:text-zinc-300",
          ].join(" ")}
          data-testid="personnel-applications-view-active"
        >
          Активные
        </button>
        <button
          type="button"
          onClick={() =>
            replaceJournalState({
              view: JOURNAL_VIEW_ARCHIVE,
              offset: 0,
              sort: "closed_at_desc",
              application_id: null,
            })
          }
          className={[
            "rounded-lg px-3 py-2 text-sm",
            isArchiveView
              ? "bg-blue-600 text-white"
              : "border border-zinc-300 text-zinc-700 dark:border-zinc-700 dark:text-zinc-300",
          ].join(" ")}
          data-testid="personnel-applications-view-archive"
        >
          Архив
        </button>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <label className="block min-w-[14rem] flex-1 text-sm">
          <span className="mb-1 block text-zinc-600 dark:text-zinc-400">Поиск</span>
          <input
            value={searchDraft}
            onChange={(e) => setSearchDraft(e.target.value)}
            placeholder="ФИО, ИИН, № обращения"
            className="w-full rounded-lg border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
            onKeyDown={(e) => {
              if (e.key === "Enter") applySearch();
            }}
            onBlur={applySearch}
            data-testid="personnel-applications-search"
          />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-zinc-600 dark:text-zinc-400">Сортировка</span>
          <select
            value={filters.sort}
            onChange={(e) => replaceJournalState({ sort: e.target.value, offset: 0 })}
            className="rounded-lg border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
            data-testid="personnel-applications-sort"
          >
            {sortOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {error ? (
        <div
          className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200"
          data-testid="personnel-applications-error"
        >
          {error}
        </div>
      ) : null}

      <PersonnelApplicationsTable
        items={items}
        loading={loading}
        archiveMode={isArchiveView}
        selectedApplicationId={selectedApplicationId}
        highlightedApplicationId={highlightedApplicationId}
        onOpen={openDetail}
        onOpenIntake={openDetail}
        workflowView={workplace === "applicants"}
      />

      {!loading && !error ? (
        <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-zinc-600 dark:text-zinc-400">
          <span data-testid="personnel-applications-total">
            Всего: {total} · страница {page} из {pageCount}
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={filters.offset <= 0 || loading}
              onClick={() => replaceJournalState({ offset: Math.max(0, filters.offset - filters.limit) })}
              className="rounded-lg border border-zinc-300 px-3 py-1.5 disabled:opacity-50 dark:border-zinc-700"
              data-testid="personnel-applications-page-prev"
            >
              Назад
            </button>
            <button
              type="button"
              disabled={filters.offset + filters.limit >= total || loading}
              onClick={() => replaceJournalState({ offset: filters.offset + filters.limit })}
              className="rounded-lg border border-zinc-300 px-3 py-1.5 disabled:opacity-50 dark:border-zinc-700"
              data-testid="personnel-applications-page-next"
            >
              Вперёд
            </button>
          </div>
        </div>
      ) : null}

      {toast ? (
        <div
          role="status"
          className={[
            "fixed bottom-4 right-4 z-[60] rounded-lg px-4 py-2 text-sm shadow-lg",
            toast.kind === "error" ? "bg-red-700 text-white" : "bg-emerald-700 text-white",
          ].join(" ")}
          data-testid="personnel-applications-toast"
        >
          {toast.message}
        </div>
      ) : null}

      <PersonnelApplicationRegisterDrawer
        open={registerOpen}
        onClose={() => setRegisterOpen(false)}
        onRegistered={handleRegistered}
        onToast={(message, kind = "success") => setToast({ message, kind })}
      />

      <PersonnelApplicationDetailDrawer
        applicationId={selectedApplicationId}
        open={detailOpen}
        journalReturnHref={journalReturnHref}
        onClose={closeDetail}
      />
    </div>
  );
}
