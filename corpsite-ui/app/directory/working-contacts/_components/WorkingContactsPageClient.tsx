// FILE: corpsite-ui/app/directory/working-contacts/_components/WorkingContactsPageClient.tsx
"use client";

import * as React from "react";
import { apiFetchJson } from "@/lib/api";
import WorkingContactsDrawer from "./WorkingContactsDrawer";
import WorkingContactsTable from "./WorkingContactsTable";

type WorkingContactItem = {
  id?: number;
  user_id?: number | null;
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
      items?: WorkingContactItem[];
      data?: WorkingContactItem[];
      total?: number;
    };

const API_BASE = "/directory/working-contacts";
const LIMIT = 100;

function normalizeItems(payload: WorkingContactsResponse): WorkingContactItem[] {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload.items)) return payload.items;
  if (Array.isArray(payload.data)) return payload.data;
  return [];
}

function extractTotal(payload: WorkingContactsResponse, items: WorkingContactItem[]): number {
  if (!Array.isArray(payload) && typeof payload.total === "number") return payload.total;
  return items.length;
}

function extractErrorMessage(error: unknown): string {
  if (typeof error === "object" && error && "message" in error) {
    const msg = String((error as { message?: unknown }).message ?? "").trim();
    if (msg) return msg;
  }
  if (error instanceof Error && error.message) return error.message;
  return "Не удалось выполнить операцию.";
}

export default function WorkingContactsPageClient() {
  const [items, setItems] = React.useState<WorkingContactItem[]>([]);
  const [total, setTotal] = React.useState(0);
  const [loading, setLoading] = React.useState(true);

  const [searchDraft, setSearchDraft] = React.useState("");
  const [appliedSearch, setAppliedSearch] = React.useState("");
  const [activeOnly, setActiveOnly] = React.useState(true);
  const [offset, setOffset] = React.useState(0);

  const [pageError, setPageError] = React.useState<string | null>(null);

  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [selectedItem, setSelectedItem] = React.useState<WorkingContactItem | null>(null);

  const loadItems = React.useCallback(async () => {
    setLoading(true);
    setPageError(null);

    try {
      const data = await apiFetchJson<WorkingContactsResponse>(API_BASE, {
        query: {
          limit: LIMIT,
          offset,
          active_only: activeOnly,
          q: appliedSearch || undefined,
        },
      });

      const normalized = normalizeItems(data);
      setItems(normalized);
      setTotal(extractTotal(data, normalized));
    } catch (error) {
      setPageError(extractErrorMessage(error));
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [offset, activeOnly, appliedSearch]);

  React.useEffect(() => {
    void loadItems();
  }, [loadItems]);

  function handleRefresh() {
    void loadItems();
  }

  function handleApplySearch(e?: React.FormEvent<HTMLFormElement>) {
    e?.preventDefault();
    setOffset(0);
    setAppliedSearch(searchDraft.trim());
  }

  function handleResetSearch() {
    setSearchDraft("");
    setAppliedSearch("");
    setOffset(0);
  }

  function handleChangePage(nextOffset: number) {
    setOffset(nextOffset);
  }

  function handleOpen(item: WorkingContactItem) {
    setSelectedItem(item);
    setDrawerOpen(true);
  }

  function handleCloseDrawer() {
    setDrawerOpen(false);
    setSelectedItem(null);
  }

  return (
    <div className="bg-[#04070f] text-zinc-100">
      <div className="mx-auto w-full max-w-[1440px] px-4 py-3">
        <div className="overflow-hidden rounded-2xl border border-zinc-800 bg-[#050816]">
          <div className="border-b border-zinc-800 px-4 py-3">
            <h1 className="text-xl font-semibold text-zinc-100">Рабочие контакты</h1>
          </div>

          <div className="border-b border-zinc-800 px-4 py-3">
            <div className="flex flex-col gap-3">
              <form
                onSubmit={handleApplySearch}
                className="flex flex-col gap-2 xl:flex-row xl:items-center"
              >
                <div className="flex-1">
                  <input
                    value={searchDraft}
                    onChange={(e) => setSearchDraft(e.target.value)}
                    placeholder="Поиск по ФИО, логину, телефону, Telegram, роли, отделению"
                    className="h-9 w-full rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 text-[13px] text-zinc-100 outline-none transition placeholder:text-zinc-500 focus:border-zinc-600"
                  />
                </div>

                <select
                  value={activeOnly ? "active" : "all"}
                  onChange={(e) => {
                    setActiveOnly(e.target.value === "active");
                    setOffset(0);
                  }}
                  className="h-9 min-w-[190px] rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 text-[13px] text-zinc-100 outline-none transition focus:border-zinc-600"
                >
                  <option value="active">Только активные</option>
                  <option value="all">Все</option>
                </select>

                <button
                  type="submit"
                  className="h-9 rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 text-[13px] text-zinc-200 transition hover:bg-zinc-900/60"
                >
                  Найти
                </button>

                <button
                  type="button"
                  onClick={handleResetSearch}
                  className="h-9 rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 text-[13px] text-zinc-200 transition hover:bg-zinc-900/60"
                >
                  Сбросить
                </button>

                <button
                  type="button"
                  onClick={handleRefresh}
                  className="h-9 rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 text-[13px] text-zinc-200 transition hover:bg-zinc-900/60"
                >
                  Обновить
                </button>
              </form>
            </div>
          </div>

          <div className="px-4 py-3">
            {!!pageError && (
              <div className="mb-3 rounded-xl border border-red-900/60 bg-red-950/40 px-4 py-3 text-sm text-red-200">
                {pageError}
              </div>
            )}

            <div className="mb-2 text-xs text-zinc-400">
              Всего: {total} · Показано: {items.length}
            </div>

            <WorkingContactsTable
              items={items}
              total={total}
              limit={LIMIT}
              offset={offset}
              loading={loading}
              onOpen={handleOpen}
              onChangePage={handleChangePage}
            />
          </div>
        </div>
      </div>

      <WorkingContactsDrawer open={drawerOpen} item={selectedItem} onClose={handleCloseDrawer} />
    </div>
  );
}