// FILE: corpsite-ui/app/directory/positions/_components/PositionsPageClient.tsx
"use client";

import * as React from "react";
import { apiFetchJson } from "../../../../lib/api";
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
    };

const API_BASE = "/directory/positions";

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

function normalizeItems(payload: PositionsResponse): PositionItem[] {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload.items)) return payload.items;
  if (Array.isArray(payload.data)) return payload.data;
  return [];
}

function extractTotal(payload: PositionsResponse, items: PositionItem[]): number {
  if (!Array.isArray(payload) && typeof payload.total === "number") return payload.total;
  return items.length;
}

function extractErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message) return error.message;
  return "Не удалось выполнить операцию.";
}

function normalizeText(value: string): string {
  return String(value || "").toLowerCase().replace(/ё/g, "е").trim();
}

function matchesSearch(name: string, query: string): boolean {
  const q = normalizeText(query);
  if (!q) return true;

  const hay = normalizeText(name);
  if (hay.includes(q)) return true;

  const tokens = q.split(/\s+/).filter(Boolean);
  return tokens.every((t) => hay.includes(t));
}

function normalizeCategoryValue(item: PositionItem): string {
  return normalizeText(String(item.category ?? ""));
}

function getCategoryLabel(item: PositionItem): string {
  const explicit = String(item.category_name ?? "").trim();
  if (explicit) return explicit;

  const raw = normalizeCategoryValue(item);
  const found = CATEGORY_OPTIONS.find((x) => x.value !== "all" && x.value === raw);
  return found?.label ?? "—";
}

export default function PositionsPageClient() {
  const [items, setItems] = React.useState<PositionItem[]>([]);
  const [total, setTotal] = React.useState(0);
  const [loading, setLoading] = React.useState(true);
  const [saving, setSaving] = React.useState(false);
  const [search, setSearch] = React.useState("");
  const [category, setCategory] = React.useState<PositionCategory>("all");
  const [pageError, setPageError] = React.useState<string | null>(null);
  const [drawerError, setDrawerError] = React.useState<string | null>(null);

  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [drawerMode, setDrawerMode] = React.useState<"create" | "edit">("create");
  const [selectedItem, setSelectedItem] = React.useState<PositionItem | null>(null);

  const loadItems = React.useCallback(async () => {
    setLoading(true);
    setPageError(null);

    try {
      const data = await apiFetchJson<PositionsResponse>(API_BASE);
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
  }, []);

  React.useEffect(() => {
    void loadItems();
  }, [loadItems]);

  const filteredItems = React.useMemo(() => {
    return items.filter((item) => {
      const bySearch = matchesSearch(item.name, search);
      const byCategory = category === "all" ? true : normalizeCategoryValue(item) === category;
      return bySearch && byCategory;
    });
  }, [items, search, category]);

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
      } else {
        const positionId = positionIdOf(selectedItem as PositionItem);
        await apiFetchJson(`${API_BASE}/${positionId}`, {
          method: "PUT",
          body: payload,
        });
      }

      setDrawerOpen(false);
      setSelectedItem(null);
      await loadItems();
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

  return (
    <div className="bg-[#04070f] text-zinc-100">
      <div className="mx-auto w-full max-w-[1440px] px-4 py-3">
        <div className="overflow-hidden rounded-2xl border border-zinc-800 bg-[#050816]">
          <div className="border-b border-zinc-800 px-4 py-3">
            <h1 className="text-xl font-semibold text-zinc-100">Должности</h1>
          </div>

          <div className="border-b border-zinc-800 px-4 py-2.5">
            <div className="flex flex-col gap-2 xl:flex-row xl:items-center">
              <div className="flex-1">
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Поиск по названию должности"
                  className="h-9 w-full rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 text-[13px] text-zinc-100 outline-none transition placeholder:text-zinc-500 focus:border-zinc-600"
                />
              </div>

              <select
                value={category}
                onChange={(e) => setCategory(e.target.value as PositionCategory)}
                className="h-9 min-w-[220px] rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 text-[13px] text-zinc-100 outline-none transition focus:border-zinc-600"
              >
                {CATEGORY_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value} className="bg-zinc-950 text-zinc-100">
                    {opt.label}
                  </option>
                ))}
              </select>

              <button
                type="button"
                onClick={() => void loadItems()}
                className="h-9 rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 text-[13px] text-zinc-200 transition hover:bg-zinc-900/60"
              >
                Обновить
              </button>

              <button
                type="button"
                onClick={openCreate}
                className="h-9 rounded-lg bg-blue-600 px-4 text-[13px] font-medium text-white transition hover:bg-blue-500"
              >
                Создать
              </button>
            </div>
          </div>

          <div className="px-4 py-3">
            {!!pageError && (
              <div className="mb-3 rounded-xl border border-red-900/60 bg-red-950/40 px-4 py-3 text-sm text-red-200">
                {pageError}
              </div>
            )}

            <div className="mb-2 text-xs text-zinc-400">
              Всего: {total} · Показано: {filteredItems.length}
            </div>

            <div className="overflow-hidden rounded-xl border border-zinc-800">
              <div className="overflow-x-auto">
                <table className="min-w-full border-collapse">
                  <thead>
                    <tr className="bg-white/[0.03] text-left">
                      <th className="w-[72px] px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-400">
                        ID
                      </th>
                      <th className="px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-400">
                        Название
                      </th>
                      <th className="w-[190px] px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-400">
                        Категория
                      </th>
                      <th className="w-[170px] px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-400">
                        Действия
                      </th>
                    </tr>
                  </thead>

                  <tbody>
                    {loading ? (
                      <tr>
                        <td colSpan={4} className="px-3 py-2.5 text-[13px] text-zinc-400">
                          Загрузка...
                        </td>
                      </tr>
                    ) : filteredItems.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="px-3 py-2.5 text-[13px] text-zinc-500">
                          Записи не найдены.
                        </td>
                      </tr>
                    ) : (
                      filteredItems.map((item) => (
                        <tr key={positionIdOf(item)} className="border-t border-zinc-800 align-middle">
                          <td className="px-3 py-1.5 text-[13px] leading-4 text-zinc-100">
                            {positionIdOf(item)}
                          </td>
                          <td className="px-3 py-1.5 text-[13px] leading-4 text-zinc-100">
                            {item.name}
                          </td>
                          <td className="px-3 py-1.5 text-[13px] leading-4 text-zinc-400">
                            {getCategoryLabel(item)}
                          </td>
                          <td className="px-3 py-1.5">
                            <div className="flex items-center gap-1.5">
                              <button
                                type="button"
                                onClick={() => openEdit(item)}
                                className="rounded-md border border-zinc-800 bg-zinc-950/40 px-2.5 py-1 text-[12px] leading-4 text-zinc-100 transition hover:bg-zinc-900/60"
                              >
                                Изменить
                              </button>

                              <button
                                type="button"
                                onClick={() => void handleDelete(item)}
                                className="rounded-md border border-red-800 bg-transparent px-2.5 py-1 text-[12px] leading-4 text-red-300 transition hover:bg-red-950/30"
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
        saving={saving}
        error={drawerError}
        onClose={closeDrawer}
        onSubmit={handleSubmit}
      />
    </div>
  );
}