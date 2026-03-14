"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";
import { apiFetchJson } from "@/lib/api";
import WorkingContactsTable from "./WorkingContactsTable";

type WorkingContactItem = {
  id?: number;
  user_id?: number | null;
  org_unit_id?: number | null;
  full_name?: string | null;
  login?: string | null;
  phone?: string | null;
  telegram_username?: string | null;
  role_name?: string | null;
  role_name_ru?: string | null;
  unit_name?: string | null;
  unit_name_ru?: string | null;
  is_active?: boolean | null;
};

type WorkingContactsResponse =
  | WorkingContactItem[]
  | {
      items?: WorkingContactItem[] | null;
      data?: WorkingContactItem[] | null;
      total?: number | null;
      filter_org_unit_id?: number | null;
      filter_org_unit_name?: string | null;
    };

const API_BASE = "/directory/working-contacts";
const PAGE_SIZE = 100;

function normalizeItems(payload: WorkingContactsResponse): WorkingContactItem[] {
  if (Array.isArray(payload)) return payload;
  if (payload && Array.isArray(payload.items)) return payload.items;
  if (payload && Array.isArray(payload.data)) return payload.data;
  return [];
}

function extractTotal(payload: WorkingContactsResponse, items: WorkingContactItem[]): number {
  if (!Array.isArray(payload) && typeof payload?.total === "number" && payload.total >= 0) {
    return payload.total;
  }
  return items.length;
}

function extractErrorMessage(error: unknown): string {
  if (typeof error === "object" && error && "message" in error) {
    const msg = String((error as { message?: unknown }).message ?? "").trim();
    if (msg) return msg;
  }
  if (error instanceof Error && error.message) return error.message;
  return "Не удалось загрузить рабочие контакты.";
}

function parsePositiveInt(value: string | null): number | null {
  const s = String(value ?? "").trim();
  if (!s) return null;
  if (!/^\d+$/.test(s)) return null;
  const n = Number(s);
  if (!Number.isSafeInteger(n) || n <= 0) return null;
  return n;
}

function readSelectedOrgUnitId(sp: ReturnType<typeof useSearchParams>): number | null {
  return (
    parsePositiveInt(sp.get("org_unit_id")) ??
    parsePositiveInt(sp.get("unit_id")) ??
    parsePositiveInt(sp.get("orgUnitId")) ??
    parsePositiveInt(sp.get("selected_org_unit_id")) ??
    parsePositiveInt(sp.get("ou")) ??
    parsePositiveInt(sp.get("unit"))
  );
}

type WorkingContactDrawerProps = {
  open: boolean;
  item: WorkingContactItem | null;
  onClose: () => void;
};

function textOrDash(value?: string | null): string {
  return String(value ?? "").trim() || "—";
}

function telegramOrDash(value?: string | null): string {
  const raw = String(value ?? "").trim();
  if (!raw) return "—";
  return raw.startsWith("@") ? raw : `@${raw}`;
}

function roleOrDash(item?: WorkingContactItem | null): string {
  return textOrDash(item?.role_name_ru ?? item?.role_name);
}

function unitOrDash(item?: WorkingContactItem | null): string {
  return textOrDash(item?.unit_name_ru ?? item?.unit_name);
}

function WorkingContactDrawer({ open, item, onClose }: WorkingContactDrawerProps) {
  React.useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && open) onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open || !item) return null;

  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative ml-auto flex h-full w-full max-w-[720px] flex-col border-l border-zinc-800 bg-[#050816] shadow-2xl">
        <div className="flex items-start justify-between border-b border-zinc-800 px-6 py-5">
          <div>
            <h2 className="text-2xl font-semibold leading-tight text-zinc-100">Рабочий контакт</h2>
            <p className="mt-1 text-sm text-zinc-400">Карточка сотрудника</p>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-zinc-800 bg-zinc-950/40 px-4 py-2 text-sm text-zinc-200 transition hover:bg-zinc-900/60"
          >
            Закрыть
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5">
          <div className="grid grid-cols-1 gap-3 rounded-xl border border-zinc-800 bg-zinc-950/30 p-4 text-sm text-zinc-300 md:grid-cols-2">
            <div>
              <div className="text-xs uppercase tracking-[0.08em] text-zinc-500">ID</div>
              <div className="mt-1 text-zinc-100">{item.id ?? item.user_id ?? "—"}</div>
            </div>

            <div>
              <div className="text-xs uppercase tracking-[0.08em] text-zinc-500">org_unit_id</div>
              <div className="mt-1 text-zinc-100">{item.org_unit_id ?? "—"}</div>
            </div>

            <div>
              <div className="text-xs uppercase tracking-[0.08em] text-zinc-500">ФИО</div>
              <div className="mt-1 text-zinc-100">{textOrDash(item.full_name)}</div>
            </div>

            <div>
              <div className="text-xs uppercase tracking-[0.08em] text-zinc-500">Логин</div>
              <div className="mt-1 text-zinc-100">{textOrDash(item.login)}</div>
            </div>

            <div>
              <div className="text-xs uppercase tracking-[0.08em] text-zinc-500">Телефон</div>
              <div className="mt-1 text-zinc-100">{textOrDash(item.phone)}</div>
            </div>

            <div>
              <div className="text-xs uppercase tracking-[0.08em] text-zinc-500">Telegram</div>
              <div className="mt-1 text-zinc-100">{telegramOrDash(item.telegram_username)}</div>
            </div>

            <div>
              <div className="text-xs uppercase tracking-[0.08em] text-zinc-500">Роль</div>
              <div className="mt-1 text-zinc-100">{roleOrDash(item)}</div>
            </div>

            <div>
              <div className="text-xs uppercase tracking-[0.08em] text-zinc-500">Отделение</div>
              <div className="mt-1 text-zinc-100">{unitOrDash(item)}</div>
            </div>

            <div>
              <div className="text-xs uppercase tracking-[0.08em] text-zinc-500">Активен</div>
              <div className="mt-1 text-zinc-100">{item.is_active ? "Да" : "Нет"}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function WorkingContactsPageClient() {
  const sp = useSearchParams();

  const orgUnitId = React.useMemo(() => readSelectedOrgUnitId(sp), [sp]);
  const orgUnitNameFromUrl = React.useMemo(() => {
    const v = String(sp.get("org_unit_name") ?? "").trim();
    return v || null;
  }, [sp]);

  const [items, setItems] = React.useState<WorkingContactItem[]>([]);
  const [total, setTotal] = React.useState<number>(0);
  const [filterOrgUnitId, setFilterOrgUnitId] = React.useState<number | null>(null);
  const [filterOrgUnitName, setFilterOrgUnitName] = React.useState<string | null>(null);

  const [loading, setLoading] = React.useState<boolean>(true);
  const [pageError, setPageError] = React.useState<string | null>(null);

  const [searchDraft, setSearchDraft] = React.useState<string>("");
  const [appliedSearch, setAppliedSearch] = React.useState<string>("");
  const [activeOnly, setActiveOnly] = React.useState<boolean>(true);
  const [offset, setOffset] = React.useState<number>(0);
  const [refreshNonce, setRefreshNonce] = React.useState<number>(0);

  const [selectedItem, setSelectedItem] = React.useState<WorkingContactItem | null>(null);
  const [drawerOpen, setDrawerOpen] = React.useState<boolean>(false);

  React.useEffect(() => {
    setOffset(0);
  }, [orgUnitId]);

  const loadItems = React.useCallback(async () => {
    setLoading(true);
    setPageError(null);

    try {
      const payload = await apiFetchJson<WorkingContactsResponse>(API_BASE, {
        query: {
          q: appliedSearch || undefined,
          active_only: activeOnly,
          org_unit_id: orgUnitId ?? undefined,
          limit: PAGE_SIZE,
          offset,
        },
      });

      const normalized = normalizeItems(payload);
      setItems(Array.isArray(normalized) ? normalized : []);
      setTotal(extractTotal(payload, normalized));

      if (!Array.isArray(payload) && payload) {
        setFilterOrgUnitId(
          payload.filter_org_unit_id != null ? Number(payload.filter_org_unit_id) : null,
        );
        setFilterOrgUnitName(
          payload.filter_org_unit_name != null
            ? String(payload.filter_org_unit_name).trim() || null
            : null,
        );
      } else {
        setFilterOrgUnitId(null);
        setFilterOrgUnitName(null);
      }
    } catch (error) {
      setPageError(extractErrorMessage(error));
      setItems([]);
      setTotal(0);
      setFilterOrgUnitId(null);
      setFilterOrgUnitName(null);
    } finally {
      setLoading(false);
    }
  }, [activeOnly, appliedSearch, offset, orgUnitId, refreshNonce]);

  React.useEffect(() => {
    void loadItems();
  }, [loadItems]);

  function handleApplySearch(e?: React.FormEvent<HTMLFormElement>) {
    e?.preventDefault();
    setOffset(0);
    setAppliedSearch(searchDraft.trim());
  }

  function handleResetSearch() {
    setSearchDraft("");
    setAppliedSearch("");
    setActiveOnly(true);
    setOffset(0);
  }

  function handleOpen(item: WorkingContactItem) {
    setSelectedItem(item);
    setDrawerOpen(true);
  }

  function handleCloseDrawer() {
    setDrawerOpen(false);
    setSelectedItem(null);
  }

  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const pages = Math.max(1, Math.ceil(Math.max(total, 1) / PAGE_SIZE));

  const filterCaption =
    filterOrgUnitName ||
    orgUnitNameFromUrl ||
    (filterOrgUnitId != null
      ? `unit #${filterOrgUnitId}`
      : orgUnitId != null
        ? `unit #${orgUnitId}`
        : null);

  return (
    <div className="bg-[#04070f] text-zinc-100">
      <div className="mx-auto w-full max-w-[1440px] px-4 py-3">
        <div className="overflow-hidden rounded-2xl border border-zinc-800 bg-[#050816]">
          <div className="border-b border-zinc-800 px-4 py-3">
            <h1 className="text-xl font-semibold leading-none text-zinc-100">
              Рабочие контакты{filterCaption ? ` (${filterCaption})` : ""}
            </h1>
          </div>

          <div className="border-b border-zinc-800 px-4 py-2">
            <form onSubmit={handleApplySearch} className="flex flex-col gap-2 xl:flex-row xl:items-center">
              <div className="flex-1">
                <input
                  value={searchDraft}
                  onChange={(e) => setSearchDraft(e.target.value)}
                  placeholder="Поиск по ID, ФИО, логину, телефону, Telegram, роли"
                  className="h-8.5 w-full rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 py-1 text-sm text-zinc-100 outline-none transition placeholder:text-zinc-500 focus:border-zinc-600"
                />
              </div>

              <label className="inline-flex h-8.5 items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 text-sm text-zinc-200">
                <input
                  type="checkbox"
                  checked={activeOnly}
                  onChange={(e) => {
                    setActiveOnly(e.target.checked);
                    setOffset(0);
                  }}
                  className="h-4 w-4"
                />
                Только активные
              </label>

              <button
                type="submit"
                className="h-8.5 rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 py-1 text-sm text-zinc-200 transition hover:bg-zinc-900/60"
              >
                Найти
              </button>

              <button
                type="button"
                onClick={handleResetSearch}
                className="h-8.5 rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 py-1 text-sm text-zinc-200 transition hover:bg-zinc-900/60"
              >
                Сбросить
              </button>

              <button
                type="button"
                onClick={() => {
                  setOffset(0);
                  setRefreshNonce((v) => v + 1);
                }}
                className="h-8.5 rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 py-1 text-sm text-zinc-200 transition hover:bg-zinc-900/60"
              >
                Обновить
              </button>
            </form>
          </div>

          <div className="px-4 py-2">
            {!!pageError && (
              <div className="mb-2 rounded-xl border border-red-900/60 bg-red-950/40 px-4 py-2 text-sm text-red-200">
                {pageError}
              </div>
            )}

            <div className="mb-1.5 flex items-center justify-between gap-2 text-[11px] text-zinc-400">
              <div>
                Всего: {total} · Показано: {items.length}
              </div>
              <div>
                Страница {page} из {pages}
                {loading ? " (обновление...)" : ""}
              </div>
            </div>

            <WorkingContactsTable
              items={items ?? []}
              total={total}
              limit={PAGE_SIZE}
              offset={offset}
              loading={loading}
              onOpen={handleOpen}
              onChangePage={setOffset}
            />
          </div>
        </div>
      </div>

      <WorkingContactDrawer open={drawerOpen} item={selectedItem} onClose={handleCloseDrawer} />
    </div>
  );
}