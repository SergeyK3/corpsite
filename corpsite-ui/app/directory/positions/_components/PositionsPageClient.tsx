// FILE: corpsite-ui/app/directory/positions/_components/PositionsPageClient.tsx
"use client";

import * as React from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import OrgScopeFilter from "@/components/OrgScopeFilter";
import OrgUnitScopeFilter from "@/components/OrgUnitScopeFilter";
import type { PositionListScope } from "@/lib/taskOrgFilters";
import { apiFetchJson } from "../../../../lib/api";
import { formatThrownError } from "@/lib/i18n";
import { readOrgScopeFromSearchParams } from "@/lib/orgScope";
import PositionDrawer from "./PositionDrawer";
import type { PositionFormValues } from "./PositionForm";

type PositionCategory = "all" | "leaders" | "medical" | "admin" | "technical" | "other";

type PositionItem = {
  position_id?: number;
  id?: number;
  name: string;
  category?: string | null;
  category_name?: string | null;
};

type PositionsResponse =
  | PositionItem[]
  | {
      items?: PositionItem[];
      data?: PositionItem[];
      total?: number;
      filter_org_unit_id?: number | null;
      filter_org_unit_name?: string | null;
    };

const API_BASE = "/directory/positions";
const PAGE_SIZE = 50;
const POSITION_SCOPE_PARAM = "position_scope";

type SearchParamsReader = Pick<URLSearchParams, "get">;

const POSITION_SCOPE_OPTIONS: Array<{ value: PositionListScope; label: string }> = [
  { value: "allowed", label: "Разрешённые" },
  { value: "used", label: "Используемые" },
];

const CATEGORY_OPTIONS: Array<{ value: PositionCategory; label: string }> = [
  { value: "all", label: "Все" },
  { value: "leaders", label: "Руководители" },
  { value: "medical", label: "Медицинские" },
  { value: "admin", label: "Административные" },
  { value: "technical", label: "Технические" },
  { value: "other", label: "Прочие" },
];

function positionIdOf(item: PositionItem): number {
  return Number(item.position_id ?? item.id ?? 0);
}

function normalizeCategoryValue(item: PositionItem): string {
  return String(item.category ?? "").trim().toLowerCase();
}

function getCategoryLabel(item: PositionItem): string {
  const explicit = String(item.category_name ?? "").trim();
  if (explicit) return explicit;

  const raw = normalizeCategoryValue(item);
  const found = CATEGORY_OPTIONS.find((x) => x.value !== "all" && x.value === raw);
  return found?.label ?? "—";
}

function extractErrorMessage(error: unknown): string {
  return formatThrownError(error, { fallback: "Не удалось выполнить операцию." });
}

function parsePositiveInt(value: string | null): number | null {
  const n = Number(String(value ?? "").trim());
  if (!Number.isFinite(n) || n <= 0) return null;
  return Math.trunc(n);
}

function readPositionListScope(
  sp: SearchParamsReader,
  orgUnitId: number | null,
): PositionListScope | null {
  if (orgUnitId == null) return null;
  const raw = String(sp.get(POSITION_SCOPE_PARAM) ?? "").trim().toLowerCase();
  if (raw === "used" || raw === "allowed") return raw;
  return "allowed";
}

export function buildPositionsListQuery(args: {
  search?: string;
  category?: PositionCategory;
  orgGroupId?: number | null;
  orgUnitId?: number | null;
  positionScope?: PositionListScope | null;
  page?: number;
  pageSize?: number;
}): Record<string, string | number | undefined> {
  const pageSize = args.pageSize ?? PAGE_SIZE;
  const page = args.page ?? 0;
  const query: Record<string, string | number | undefined> = {
    limit: pageSize,
    offset: page * pageSize,
  };

  const search = String(args.search ?? "").trim();
  if (search) query.q = search;

  if (args.category && args.category !== "all") {
    query.category = args.category;
  }

  if (args.orgGroupId != null && args.orgUnitId == null) {
    query.org_group_id = args.orgGroupId;
  }

  if (args.orgUnitId != null) {
    query.org_unit_id = args.orgUnitId;
    query.scope = args.positionScope ?? "allowed";
  }

  return query;
}

function positionScopeLabel(scope: PositionListScope | null): string | null {
  if (scope == null) return null;
  return POSITION_SCOPE_OPTIONS.find((opt) => opt.value === scope)?.label ?? null;
}

function readSelectedOrgUnitId(sp: SearchParamsReader): number | null {
  return (
    parsePositiveInt(sp.get("org_unit_id")) ??
    parsePositiveInt(sp.get("unit_id")) ??
    parsePositiveInt(sp.get("orgUnitId")) ??
    parsePositiveInt(sp.get("selected_org_unit_id")) ??
    parsePositiveInt(sp.get("ou")) ??
    parsePositiveInt(sp.get("unit"))
  );
}

function normalizeItems(payload: PositionsResponse): {
  items: PositionItem[];
  total: number;
  filterOrgUnitId: number | null;
  filterOrgUnitName: string | null;
} {
  if (Array.isArray(payload)) {
    return {
      items: payload,
      total: payload.length,
      filterOrgUnitId: null,
      filterOrgUnitName: null,
    };
  }

  const items = Array.isArray(payload.items)
    ? payload.items
    : Array.isArray(payload.data)
      ? payload.data
      : [];

  const total = Number(payload.total ?? items.length ?? 0);
  const rawFilterOrgUnitId = payload.filter_org_unit_id;
  const filterOrgUnitId = rawFilterOrgUnitId == null ? null : Number(rawFilterOrgUnitId);
  const rawFilterOrgUnitName = payload.filter_org_unit_name;
  const filterOrgUnitName =
    rawFilterOrgUnitName == null ? null : String(rawFilterOrgUnitName).trim();

  return {
    items,
    total: Number.isFinite(total) ? total : items.length,
    filterOrgUnitId: Number.isFinite(filterOrgUnitId ?? NaN) ? filterOrgUnitId : null,
    filterOrgUnitName: filterOrgUnitName || null,
  };
}

export default function PositionsPageClient() {
  const sp = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const searchParamsKey = sp.toString();
  const parsedSearchParams = React.useMemo(
    () => new URLSearchParams(searchParamsKey),
    [searchParamsKey],
  );

  const orgScope = React.useMemo(
    () => readOrgScopeFromSearchParams(parsedSearchParams),
    [parsedSearchParams],
  );
  const orgGroupId = orgScope.org_group_id;
  const orgUnitId = React.useMemo(
    () => readSelectedOrgUnitId(parsedSearchParams),
    [parsedSearchParams],
  );
  const hasOrgUnitFilter = orgUnitId != null;
  const urlPositionScope = React.useMemo(
    () => readPositionListScope(parsedSearchParams, orgUnitId),
    [parsedSearchParams, orgUnitId],
  );

  const [localPositionScope, setLocalPositionScope] = React.useState<PositionListScope | null>(null);
  const pendingScopeTransitionRef = React.useRef<PositionListScope | null>(null);
  const prevOrgUnitIdRef = React.useRef<number | null | undefined>(orgUnitId);

  const positionScope = React.useMemo(() => {
    if (!hasOrgUnitFilter) return null;
    if (localPositionScope != null) return localPositionScope;
    return urlPositionScope;
  }, [hasOrgUnitFilter, localPositionScope, urlPositionScope]);

  const positionScopeCaption = positionScopeLabel(positionScope);
  const orgUnitNameFromUrl = React.useMemo(() => {
    const v = String(parsedSearchParams.get("org_unit_name") ?? "").trim();
    return v || null;
  }, [parsedSearchParams]);

  const loadSeqRef = React.useRef(0);

  const [items, setItems] = React.useState<PositionItem[]>([]);
  const [total, setTotal] = React.useState(0);
  const [filterOrgUnitId, setFilterOrgUnitId] = React.useState<number | null>(null);
  const [filterOrgUnitName, setFilterOrgUnitName] = React.useState<string | null>(null);

  const [loading, setLoading] = React.useState(true);
  const [saving, setSaving] = React.useState(false);

  const [searchInput, setSearchInput] = React.useState("");
  const [search, setSearch] = React.useState("");

  const [category, setCategory] = React.useState<PositionCategory>("all");
  const [page, setPage] = React.useState(0);

  const [pageError, setPageError] = React.useState<string | null>(null);
  const [drawerError, setDrawerError] = React.useState<string | null>(null);

  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [drawerMode, setDrawerMode] = React.useState<"create" | "edit">("create");
  const [selectedItem, setSelectedItem] = React.useState<PositionItem | null>(null);

  React.useEffect(() => {
    const timer = window.setTimeout(() => {
      const next = searchInput.trim();
      setPage(0);
      setSearch(next);
    }, 250);

    return () => window.clearTimeout(timer);
  }, [searchInput]);

  React.useEffect(() => {
    setPage(0);
  }, [orgGroupId, orgUnitId, positionScope]);

  React.useEffect(() => {
    if (prevOrgUnitIdRef.current !== orgUnitId) {
      prevOrgUnitIdRef.current = orgUnitId;
      pendingScopeTransitionRef.current = null;
      setLocalPositionScope(orgUnitId == null ? null : urlPositionScope);
      return;
    }

    if (orgUnitId == null) {
      pendingScopeTransitionRef.current = null;
      setLocalPositionScope(null);
      return;
    }

    const pendingScope = pendingScopeTransitionRef.current;
    if (pendingScope != null) {
      if (urlPositionScope === pendingScope) {
        pendingScopeTransitionRef.current = null;
      }
      return;
    }

    setLocalPositionScope(urlPositionScope);
  }, [orgUnitId, urlPositionScope, searchParamsKey]);

  React.useEffect(() => {
    if (orgUnitId == null) return;
    if (pendingScopeTransitionRef.current != null) return;
    const raw = String(parsedSearchParams.get(POSITION_SCOPE_PARAM) ?? "").trim().toLowerCase();
    if (raw === "used" || raw === "allowed") return;

    const params = new URLSearchParams(searchParamsKey);
    params.set(POSITION_SCOPE_PARAM, "allowed");
    const query = params.toString();
    router.replace(query ? `${pathname}?${query}` : pathname);
    pendingScopeTransitionRef.current = "allowed";
    setLocalPositionScope("allowed");
  }, [orgUnitId, pathname, parsedSearchParams, router, searchParamsKey]);

  const loadItems = React.useCallback(async () => {
    const seq = ++loadSeqRef.current;
    setLoading(true);
    setPageError(null);

    try {
      const payload = await apiFetchJson<PositionsResponse>(API_BASE, {
        query: buildPositionsListQuery({
          search,
          category,
          orgGroupId,
          orgUnitId,
          positionScope,
          page,
        }),
      });

      if (seq !== loadSeqRef.current) return;

      const normalized = normalizeItems(payload);
      setItems(normalized.items);
      setTotal(normalized.total);
      setFilterOrgUnitId(normalized.filterOrgUnitId);
      setFilterOrgUnitName(normalized.filterOrgUnitName);
    } catch (error) {
      if (seq !== loadSeqRef.current) return;
      setPageError(extractErrorMessage(error));
      setItems([]);
      setTotal(0);
      setFilterOrgUnitId(null);
      setFilterOrgUnitName(null);
    } finally {
      if (seq === loadSeqRef.current) setLoading(false);
    }
  }, [search, category, orgGroupId, orgUnitId, positionScope, page]);

  const setPositionScope = React.useCallback(
    (nextScope: PositionListScope) => {
      pendingScopeTransitionRef.current = nextScope;
      setLocalPositionScope(nextScope);
      setPage(0);

      const params = new URLSearchParams(searchParamsKey);
      params.set(POSITION_SCOPE_PARAM, nextScope);
      params.delete("offset");
      const query = params.toString();
      router.replace(query ? `${pathname}?${query}` : pathname);
    },
    [pathname, router, searchParamsKey],
  );

  React.useEffect(() => {
    void loadItems();
  }, [loadItems]);

  React.useEffect(() => {
    if (page > 0 && total > 0 && page * PAGE_SIZE >= total) {
      setPage(Math.max(0, Math.ceil(total / PAGE_SIZE) - 1));
    }
  }, [page, total]);

  function openCreate() {
    setDrawerError(null);
    setSelectedItem(null);
    setDrawerMode("create");
    setDrawerOpen(true);
  }

  function openEdit(item: PositionItem) {
    setDrawerError(null);
    setSelectedItem(item);
    setDrawerMode("edit");
    setDrawerOpen(true);
  }

  function closeDrawer() {
    if (saving) return;
    setDrawerOpen(false);
    setDrawerError(null);
    setSelectedItem(null);
  }

  async function handleSubmit(values: PositionFormValues) {
    setSaving(true);
    setDrawerError(null);

    try {
      const payload = {
        name: values.name.trim(),
        category: values.category,
      };

      if (drawerMode === "create") {
        await apiFetchJson(API_BASE, {
          method: "POST",
          body: payload,
        });

        setDrawerOpen(false);
        setSelectedItem(null);

        if (page !== 0) {
          setPage(0);
        } else {
          await loadItems();
        }
      } else {
        const positionId = positionIdOf(selectedItem as PositionItem);
        await apiFetchJson(`${API_BASE}/${positionId}`, {
          method: "PUT",
          body: payload,
        });

        setDrawerOpen(false);
        setSelectedItem(null);
        await loadItems();
      }
    } catch (error) {
      setDrawerError(extractErrorMessage(error));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(item: PositionItem) {
    const positionId = positionIdOf(item);
    const ok = window.confirm(`Удалить должность «${item.name}»?`);
    if (!ok) return;

    setPageError(null);

    try {
      await apiFetchJson(`${API_BASE}/${positionId}`, { method: "DELETE" });
      await loadItems();
    } catch (error) {
      setPageError(extractErrorMessage(error));
    }
  }

  const pageFrom = total === 0 ? 0 : page * PAGE_SIZE + 1;
  const pageTo = Math.min(total, page * PAGE_SIZE + items.length);
  const hasPrev = page > 0;
  const hasNext = (page + 1) * PAGE_SIZE < total;

  const filterCaption =
    filterOrgUnitName ||
    orgUnitNameFromUrl ||
    (filterOrgUnitId != null
      ? `unit #${filterOrgUnitId}`
      : orgUnitId != null
        ? `unit #${orgUnitId}`
        : null);

  return (
    <div className="bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50">
      <div className="mx-auto w-full max-w-[1440px] px-4 py-3">
        <div className="overflow-hidden rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950">
          <div className="border-b border-zinc-200 dark:border-zinc-800 px-4 py-3">
            <h1 className="text-xl font-semibold leading-none text-zinc-900 dark:text-zinc-50">
              Должности{filterCaption ? ` (${filterCaption})` : ""}
            </h1>
          </div>

          <div className="border-b border-zinc-200 dark:border-zinc-800 px-4 py-2">
            <div className="flex flex-col gap-2 xl:flex-row xl:items-end">
              <OrgScopeFilter
                basePath="/directory/positions"
                className="min-w-[240px]"
                resetParamsOnChange={["offset", "org_unit_id", "org_unit_name", POSITION_SCOPE_PARAM]}
              />

              <OrgUnitScopeFilter
                basePath="/directory/positions"
                className="min-w-[240px]"
                resetParamsOnChange={["offset", POSITION_SCOPE_PARAM]}
              />

              {hasOrgUnitFilter ? (
                <div
                  className="flex items-center gap-1 rounded-lg border border-zinc-200 bg-zinc-100 p-0.5 dark:border-zinc-800 dark:bg-zinc-900"
                  data-testid="positions-scope-toggle"
                >
                  {POSITION_SCOPE_OPTIONS.map((option) => {
                    const active = positionScope === option.value;
                    return (
                      <button
                        key={option.value}
                        type="button"
                        data-testid={`positions-scope-${option.value}`}
                        aria-pressed={active}
                        onClick={() => setPositionScope(option.value)}
                        className={`rounded-md px-2.5 py-1 text-xs font-medium transition ${
                          active
                            ? "bg-white text-zinc-900 shadow-sm dark:bg-zinc-950 dark:text-zinc-50"
                            : "text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
                        }`}
                      >
                        {option.label}
                      </button>
                    );
                  })}
                </div>
              ) : orgGroupId != null ? (
                <div
                  className="flex h-8.5 items-center rounded-lg border border-dashed border-zinc-300 px-2.5 text-xs text-zinc-600 dark:border-zinc-700 dark:text-zinc-400"
                  data-testid="positions-scope-hint"
                >
                  Выберите подразделение
                </div>
              ) : null}

              <div className="flex-1">
                <input
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  placeholder="Поиск по названию должности"
                  className="h-8.5 w-full rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 py-1 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400"
                />
              </div>

              <select
                value={category}
                onChange={(e) => {
                  setCategory(e.target.value as PositionCategory);
                  setPage(0);
                }}
                className="h-8.5 min-w-[220px] rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 py-1 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition focus:border-zinc-400"
              >
                {CATEGORY_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value} className="bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50">
                    {opt.label}
                  </option>
                ))}
              </select>

              <button
                type="button"
                onClick={() => void loadItems()}
                className="h-8.5 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 py-1 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700"
              >
                Обновить
              </button>

              <button
                type="button"
                onClick={openCreate}
                className="h-8.5 rounded-lg bg-blue-600 px-3.5 py-1 text-sm font-medium text-white transition hover:bg-blue-500"
              >
                Создать
              </button>
            </div>
          </div>

          <div className="px-4 py-2">
            {!!pageError && (
              <div className="mb-2 rounded-xl border border-red-200 dark:border-red-900/55 bg-red-50 dark:bg-red-950/35 px-4 py-2 text-sm text-red-800 dark:text-red-200">
                {pageError}
              </div>
            )}

            <div className="mb-1.5 flex flex-col gap-1 text-[11px] text-zinc-600 dark:text-zinc-400 md:flex-row md:items-center md:justify-between">
              <div>
                {positionScopeCaption ? (
                  <span className="font-medium text-zinc-700 dark:text-zinc-300">
                    Режим: {positionScopeCaption}
                  </span>
                ) : null}
                {positionScopeCaption ? <span className="mx-2">·</span> : null}
                Всего: {total}
                {total > 0 ? <span className="ml-2">· показано: {pageFrom}–{pageTo}</span> : null}
              </div>

              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  onClick={() => setPage((prev) => Math.max(0, prev - 1))}
                  disabled={!hasPrev || loading}
                  className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-2 py-0.5 text-[10px] text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Назад
                </button>

                <div className="min-w-[52px] text-center text-[10px] text-zinc-600 dark:text-zinc-400">
                  Стр. {page + 1}
                </div>

                <button
                  type="button"
                  onClick={() => setPage((prev) => prev + 1)}
                  disabled={!hasNext || loading}
                  className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-2 py-0.5 text-[10px] text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Вперёд
                </button>
              </div>
            </div>

            <div className="overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800">
              <div className="overflow-x-auto">
                <table className="min-w-full border-collapse">
                  <thead>
                    <tr className="bg-zinc-100 dark:bg-zinc-900 text-left">
                      <th className="w-[72px] px-3 py-1 text-[10px] font-medium uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">
                        ID
                      </th>
                      <th className="px-3 py-1 text-[10px] font-medium uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">
                        Название
                      </th>
                      <th className="w-[190px] px-3 py-1 text-[10px] font-medium uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">
                        Категория
                      </th>
                      <th className="w-[170px] px-3 py-1 text-[10px] font-medium uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">
                        Действия
                      </th>
                    </tr>
                  </thead>

                  <tbody>
                    {loading ? (
                      <tr>
                        <td colSpan={4} className="px-3 py-2 text-[13px] text-zinc-600 dark:text-zinc-400">
                          Загрузка...
                        </td>
                      </tr>
                    ) : items.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="px-3 py-2 text-[13px] text-zinc-600 dark:text-zinc-400">
                          Записи не найдены.
                        </td>
                      </tr>
                    ) : (
                      items.map((item) => (
                        <tr key={positionIdOf(item)} className="border-t border-zinc-200 dark:border-zinc-800 align-middle">
                          <td className="px-3 py-1 text-[13px] leading-4 text-zinc-900 dark:text-zinc-50">
                            {positionIdOf(item)}
                          </td>
                          <td className="px-3 py-1 text-[13px] leading-4 text-zinc-900 dark:text-zinc-50">
                            {item.name}
                          </td>
                          <td className="px-3 py-1 text-[13px] leading-4 text-zinc-600 dark:text-zinc-400">
                            {getCategoryLabel(item)}
                          </td>
                          <td className="px-3 py-1">
                            <div className="flex items-center gap-1">
                              <button
                                type="button"
                                onClick={() => openEdit(item)}
                                className="rounded-md border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-2 py-0.5 text-[10px] leading-4 text-zinc-900 dark:text-zinc-50 transition hover:bg-zinc-200 dark:hover:bg-zinc-700"
                              >
                                Изменить
                              </button>

                              <button
                                type="button"
                                onClick={() => void handleDelete(item)}
                                className="rounded-md border border-red-300 dark:border-red-800 bg-transparent px-2 py-0.5 text-[10px] leading-4 text-red-700 dark:text-red-300 transition hover:bg-red-50 dark:bg-red-950/35"
                              >
                                Удалить
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </div>

      <PositionDrawer
        open={drawerOpen}
        mode={drawerMode}
        position={selectedItem}
        orgUnitLabel={filterCaption}
        saving={saving}
        error={drawerError}
        onClose={closeDrawer}
        onSubmit={handleSubmit}
      />
    </div>
  );
}