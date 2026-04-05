// FILE: corpsite-ui/app/directory/contacts/page.tsx
"use client";

import * as React from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { apiFetchJson } from "@/lib/api";

type ContactItem = {
  contact_id: number;
  person_id?: number | null;
  full_name?: string | null;
  phone?: string | null;
  telegram_username?: string | null;
  telegram_numeric_id?: number | null;
  created_at?: string | null;
  updated_at?: string | null;
};

type ContactsResponse =
  | ContactItem[]
  | {
      items?: ContactItem[];
      data?: ContactItem[];
      total?: number;
      filter_org_unit_id?: number | null;
      filter_org_unit_name?: string | null;
    };

type ContactFormValues = {
  full_name: string;
  person_id: string;
  phone: string;
  telegram_username: string;
  telegram_numeric_id: string;
};

const API_BASE = "/directory/contacts";
const PAGE_SIZE = 100;
const ORG_FILTER_PARAM_KEYS = [
  "org_unit_id",
  "unit_id",
  "orgUnitId",
  "selected_org_unit_id",
  "ou",
  "unit",
  "org_unit_name",
] as const;

function normalizeItems(payload: ContactsResponse): ContactItem[] {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload.items)) return payload.items;
  if (Array.isArray(payload.data)) return payload.data;
  return [];
}

function extractTotal(payload: ContactsResponse, items: ContactItem[]): number {
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

function parseOptionalPositiveInt(value: string): number | null {
  const s = String(value || "").trim();
  if (!s) return null;
  if (!/^\d+$/.test(s)) return null;
  const n = Number(s);
  if (!Number.isSafeInteger(n) || n <= 0) return null;
  return n;
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

function formatTelegramUsername(value?: string | null): string {
  const raw = String(value ?? "").trim();
  if (!raw) return "—";
  return raw.startsWith("@") ? raw : `@${raw}`;
}

function formatDateTime(value?: string | null): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleString("ru-RU");
}

function toFormValues(item?: ContactItem | null): ContactFormValues {
  return {
    full_name: String(item?.full_name ?? "").trim(),
    person_id: item?.person_id != null ? String(item.person_id) : "",
    phone: String(item?.phone ?? "").trim(),
    telegram_username: String(item?.telegram_username ?? "").trim(),
    telegram_numeric_id: item?.telegram_numeric_id != null ? String(item.telegram_numeric_id) : "",
  };
}

function buildUrlWithoutOrgFilter(
  pathname: string,
  sp: ReturnType<typeof useSearchParams>,
): string {
  const params = new URLSearchParams(sp.toString());
  for (const key of ORG_FILTER_PARAM_KEYS) {
    params.delete(key);
  }
  const query = params.toString();
  return query ? `${pathname}?${query}` : pathname;
}

function ContactDrawer({
  open,
  mode,
  initialValues,
  currentItem,
  saving,
  error,
  onClose,
  onSubmit,
}: {
  open: boolean;
  mode: "create" | "edit";
  initialValues: ContactFormValues;
  currentItem: ContactItem | null;
  saving: boolean;
  error: string | null;
  onClose: () => void;
  onSubmit: (values: ContactFormValues) => Promise<void> | void;
}) {
  const [values, setValues] = React.useState<ContactFormValues>(initialValues);

  React.useEffect(() => {
    setValues(initialValues);
  }, [initialValues]);

  React.useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && open && !saving) onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, saving, onClose]);

  if (!open) return null;

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    await onSubmit({
      full_name: values.full_name.trim(),
      person_id: values.person_id.trim(),
      phone: values.phone.trim(),
      telegram_username: values.telegram_username.trim(),
      telegram_numeric_id: values.telegram_numeric_id.trim(),
    });
  }

  return (
    <div className="fixed inset-0 z-50 flex">
      <div
        className="absolute inset-0 bg-zinc-600/35 backdrop-blur-sm"
        onClick={saving ? undefined : onClose}
      />
      <div className="relative ml-auto flex h-full w-full max-w-[760px] flex-col border-l border-zinc-200 bg-white shadow-2xl">
        <form onSubmit={handleSubmit} className="flex h-full flex-col bg-white text-zinc-900">
          <div className="flex items-start justify-between border-b border-zinc-200 px-6 py-5">
            <div>
              <h2 className="text-2xl font-semibold leading-tight text-zinc-900">
                {mode === "create" ? "Создание контакта" : "Редактирование контакта"}
              </h2>
              <p className="mt-1 text-sm text-zinc-600">Справочник контактов</p>
            </div>

            <button
              type="button"
              onClick={onClose}
              disabled={saving}
              className="rounded-lg border border-zinc-200 bg-zinc-100 px-4 py-2 text-sm text-zinc-800 transition hover:bg-zinc-200 disabled:opacity-60"
            >
              Закрыть
            </button>
          </div>

          <div className="flex-1 overflow-y-auto px-6 py-5">
            <div className="mx-auto flex w-full max-w-3xl flex-col gap-5">
              {!!error && (
                <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
                  {error}
                </div>
              )}

              {mode === "edit" && currentItem ? (
                <div className="grid grid-cols-1 gap-3 rounded-xl border border-zinc-200 bg-zinc-50 p-4 text-sm text-zinc-700 md:grid-cols-2">
                  <div>
                    <div className="text-xs uppercase tracking-[0.08em] text-zinc-600">ID</div>
                    <div className="mt-1 text-zinc-900">{currentItem.contact_id}</div>
                  </div>
                  <div>
                    <div className="text-xs uppercase tracking-[0.08em] text-zinc-600">person_id</div>
                    <div className="mt-1 text-zinc-900">
                      {currentItem.person_id != null ? currentItem.person_id : "—"}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs uppercase tracking-[0.08em] text-zinc-600">Создан</div>
                    <div className="mt-1 text-zinc-900">{formatDateTime(currentItem.created_at)}</div>
                  </div>
                  <div>
                    <div className="text-xs uppercase tracking-[0.08em] text-zinc-600">Обновлён</div>
                    <div className="mt-1 text-zinc-900">{formatDateTime(currentItem.updated_at)}</div>
                  </div>
                </div>
              ) : null}

              <div className="flex flex-col gap-2">
                <label htmlFor="full_name" className="text-sm font-medium text-zinc-800">
                  ФИО / название контакта <span className="text-red-400">*</span>
                </label>
                <input
                  id="full_name"
                  name="full_name"
                  type="text"
                  value={values.full_name}
                  onChange={(e) => setValues((prev) => ({ ...prev, full_name: e.target.value }))}
                  placeholder="Например: Иванов Иван Иванович"
                  autoComplete="off"
                  spellCheck={false}
                  className="h-11 rounded-lg border border-zinc-200 bg-zinc-100 px-4 py-2 text-sm text-zinc-900 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400"
                  required
                />
              </div>

              <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                <div className="flex flex-col gap-2">
                  <label htmlFor="person_id" className="text-sm font-medium text-zinc-800">
                    person_id
                  </label>
                  <input
                    id="person_id"
                    name="person_id"
                    type="text"
                    inputMode="numeric"
                    value={values.person_id}
                    onChange={(e) => setValues((prev) => ({ ...prev, person_id: e.target.value }))}
                    placeholder="Например: 25"
                    autoComplete="off"
                    spellCheck={false}
                    className="h-11 rounded-lg border border-zinc-200 bg-zinc-100 px-4 py-2 text-sm text-zinc-900 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400"
                  />
                </div>

                <div className="flex flex-col gap-2">
                  <label htmlFor="phone" className="text-sm font-medium text-zinc-800">
                    Телефон
                  </label>
                  <input
                    id="phone"
                    name="phone"
                    type="text"
                    value={values.phone}
                    onChange={(e) => setValues((prev) => ({ ...prev, phone: e.target.value }))}
                    placeholder="+7 777 000 00 00"
                    autoComplete="off"
                    spellCheck={false}
                    className="h-11 rounded-lg border border-zinc-200 bg-zinc-100 px-4 py-2 text-sm text-zinc-900 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                <div className="flex flex-col gap-2">
                  <label htmlFor="telegram_username" className="text-sm font-medium text-zinc-800">
                    Telegram username
                  </label>
                  <input
                    id="telegram_username"
                    name="telegram_username"
                    type="text"
                    value={values.telegram_username}
                    onChange={(e) =>
                      setValues((prev) => ({ ...prev, telegram_username: e.target.value }))
                    }
                    placeholder="@username"
                    autoComplete="off"
                    spellCheck={false}
                    className="h-11 rounded-lg border border-zinc-200 bg-zinc-100 px-4 py-2 text-sm text-zinc-900 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400"
                  />
                </div>

                <div className="flex flex-col gap-2">
                  <label htmlFor="telegram_numeric_id" className="text-sm font-medium text-zinc-800">
                    Telegram numeric id
                  </label>
                  <input
                    id="telegram_numeric_id"
                    name="telegram_numeric_id"
                    type="text"
                    inputMode="numeric"
                    value={values.telegram_numeric_id}
                    onChange={(e) =>
                      setValues((prev) => ({ ...prev, telegram_numeric_id: e.target.value }))
                    }
                    placeholder="Например: 885342581"
                    autoComplete="off"
                    spellCheck={false}
                    className="h-11 rounded-lg border border-zinc-200 bg-zinc-100 px-4 py-2 text-sm text-zinc-900 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400"
                  />
                </div>
              </div>
            </div>
          </div>

          <div className="flex items-center justify-end gap-3 border-t border-zinc-200 px-6 py-4">
            <button
              type="button"
              onClick={onClose}
              disabled={saving}
              className="rounded-lg border border-zinc-200 bg-zinc-100 px-4 py-2 text-sm text-zinc-800 transition hover:bg-zinc-200 disabled:opacity-60"
            >
              Закрыть
            </button>

            <button
              type="submit"
              disabled={saving}
              className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {saving ? "Сохранение..." : "Сохранить"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function ContactsPage() {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();

  const orgUnitId = React.useMemo(() => readSelectedOrgUnitId(sp), [sp]);
  const orgUnitNameFromUrl = React.useMemo(() => {
    const v = String(sp.get("org_unit_name") ?? "").trim();
    return v || null;
  }, [sp]);

  const [items, setItems] = React.useState<ContactItem[]>([]);
  const [total, setTotal] = React.useState(0);
  const [filterOrgUnitId, setFilterOrgUnitId] = React.useState<number | null>(null);
  const [filterOrgUnitName, setFilterOrgUnitName] = React.useState<string | null>(null);

  const [loading, setLoading] = React.useState(true);
  const [saving, setSaving] = React.useState(false);

  const [searchDraft, setSearchDraft] = React.useState("");
  const [appliedSearch, setAppliedSearch] = React.useState("");
  const [offset, setOffset] = React.useState(0);
  const [refreshNonce, setRefreshNonce] = React.useState(0);

  const [pageError, setPageError] = React.useState<string | null>(null);
  const [drawerError, setDrawerError] = React.useState<string | null>(null);

  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [drawerMode, setDrawerMode] = React.useState<"create" | "edit">("create");
  const [selectedItem, setSelectedItem] = React.useState<ContactItem | null>(null);

  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const pages = Math.max(1, Math.ceil(Math.max(total, 1) / PAGE_SIZE));

  React.useEffect(() => {
    setOffset(0);
  }, [orgUnitId]);

  const loadItems = React.useCallback(async () => {
    setLoading(true);
    setPageError(null);

    try {
      const data = await apiFetchJson<ContactsResponse>(API_BASE, {
        query: {
          q: appliedSearch || undefined,
          org_unit_id: orgUnitId ?? undefined,
          limit: PAGE_SIZE,
          offset,
        },
      });

      const normalized = normalizeItems(data);
      setItems(normalized);
      setTotal(extractTotal(data, normalized));

      if (!Array.isArray(data)) {
        setFilterOrgUnitId(
          data.filter_org_unit_id != null ? Number(data.filter_org_unit_id) : null,
        );
        setFilterOrgUnitName(
          data.filter_org_unit_name != null
            ? String(data.filter_org_unit_name).trim() || null
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
  }, [appliedSearch, orgUnitId, offset, refreshNonce]);

  React.useEffect(() => {
    void loadItems();
  }, [loadItems]);

  function openCreate() {
    setDrawerError(null);
    setSelectedItem(null);
    setDrawerMode("create");
    setDrawerOpen(true);
  }

  function openEdit(item: ContactItem) {
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

  async function handleSubmit(values: ContactFormValues) {
    setSaving(true);
    setDrawerError(null);

    try {
      const personId = parseOptionalPositiveInt(values.person_id);
      if (values.person_id.trim() && personId === null) {
        throw new Error("person_id должен быть положительным целым числом.");
      }

      const telegramNumericId = parseOptionalPositiveInt(values.telegram_numeric_id);
      if (values.telegram_numeric_id.trim() && telegramNumericId === null) {
        throw new Error("telegram_numeric_id должен быть положительным целым числом.");
      }

      const payload = {
        full_name: values.full_name.trim(),
        person_id: personId,
        phone: values.phone.trim() || null,
        telegram_username: values.telegram_username.trim() || null,
        telegram_numeric_id: telegramNumericId,
      };

      if (drawerMode === "create") {
        await apiFetchJson(API_BASE, {
          method: "POST",
          body: payload,
        });
      } else {
        await apiFetchJson(`${API_BASE}/${selectedItem?.contact_id}`, {
          method: "PATCH",
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

  async function handleDelete(item: ContactItem) {
    const ok = window.confirm(
      `Удалить контакт «${String(item.full_name ?? "").trim() || item.contact_id}»?`,
    );
    if (!ok) return;

    setPageError(null);

    try {
      await apiFetchJson(`${API_BASE}/${item.contact_id}`, { method: "DELETE" });

      if (items.length === 1 && offset > 0) {
        setOffset((prev) => Math.max(0, prev - PAGE_SIZE));
      } else {
        await loadItems();
      }
    } catch (error) {
      setPageError(extractErrorMessage(error));
    }
  }

  function handleApplySearch(e?: React.FormEvent<HTMLFormElement>) {
    e?.preventDefault();
    setOffset(0);
    setAppliedSearch(searchDraft.trim());
  }

  function handleRefresh() {
    setSearchDraft("");
    setAppliedSearch("");
    setOffset(0);
    setPageError(null);
    setFilterOrgUnitId(null);
    setFilterOrgUnitName(null);

    const nextUrl = buildUrlWithoutOrgFilter(pathname, sp);
    const currentUrl = sp.toString() ? `${pathname}?${sp.toString()}` : pathname;

    if (nextUrl !== currentUrl) {
      router.replace(nextUrl);
      return;
    }

    setRefreshNonce((v) => v + 1);
  }

  const filterCaption =
    filterOrgUnitName ||
    orgUnitNameFromUrl ||
    (filterOrgUnitId != null
      ? `unit #${filterOrgUnitId}`
      : orgUnitId != null
        ? `unit #${orgUnitId}`
        : null);

  return (
    <div className="bg-zinc-50 text-zinc-900">
      <div className="mx-auto w-full max-w-[1440px] px-4 py-3">
        <div className="overflow-hidden rounded-2xl border border-zinc-200 bg-white">
          <div className="border-b border-zinc-200 px-4 py-3">
            <h1 className="text-xl font-semibold leading-none text-zinc-900">
              Контакты{filterCaption ? ` (${filterCaption})` : ""}
            </h1>
          </div>

          <div className="border-b border-zinc-200 px-4 py-2">
            <form onSubmit={handleApplySearch} className="flex flex-col gap-2 xl:flex-row xl:items-center">
              <div className="flex-1">
                <input
                  value={searchDraft}
                  onChange={(e) => setSearchDraft(e.target.value)}
                  placeholder="Поиск по ID, person_id, ФИО, телефону, Telegram"
                  className="h-8.5 w-full rounded-lg border border-zinc-200 bg-zinc-100 px-3 py-1 text-sm text-zinc-900 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400"
                />
              </div>

              <button
                type="submit"
                className="h-8.5 rounded-lg border border-zinc-200 bg-zinc-100 px-3 py-1 text-sm text-zinc-800 transition hover:bg-zinc-200"
              >
                Найти
              </button>

              <button
                type="button"
                onClick={handleRefresh}
                className="h-8.5 rounded-lg border border-zinc-200 bg-zinc-100 px-3 py-1 text-sm text-zinc-800 transition hover:bg-zinc-200"
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
            </form>
          </div>

          <div className="px-4 py-2">
            {!!pageError && (
              <div className="mb-2 rounded-xl border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-800">
                {pageError}
              </div>
            )}

            <div className="mb-1.5 flex items-center justify-between gap-2 text-[11px] text-zinc-600">
              <div>
                Всего: {total} · Показано: {items.length}
              </div>
              <div>
                Страница {page} из {pages}
                {loading ? " (обновление...)" : ""}
              </div>
            </div>

            <div className="overflow-hidden rounded-xl border border-zinc-200">
              <div className="overflow-x-auto">
                <table className="min-w-full border-collapse">
                  <thead>
                    <tr className="bg-zinc-100 text-left">
                      <th className="w-[72px] px-3 py-1 text-[10px] font-medium uppercase tracking-[0.08em] text-zinc-600">
                        ID
                      </th>
                      <th className="min-w-[280px] px-3 py-1 text-[10px] font-medium uppercase tracking-[0.08em] text-zinc-600">
                        ФИО
                      </th>
                      <th className="min-w-[120px] px-3 py-1 text-[10px] font-medium uppercase tracking-[0.08em] text-zinc-600">
                        person_id
                      </th>
                      <th className="min-w-[180px] px-3 py-1 text-[10px] font-medium uppercase tracking-[0.08em] text-zinc-600">
                        Телефон
                      </th>
                      <th className="min-w-[180px] px-3 py-1 text-[10px] font-medium uppercase tracking-[0.08em] text-zinc-600">
                        Telegram
                      </th>
                      <th className="min-w-[180px] px-3 py-1 text-[10px] font-medium uppercase tracking-[0.08em] text-zinc-600">
                        Telegram ID
                      </th>
                      <th className="w-[190px] px-3 py-1 text-[10px] font-medium uppercase tracking-[0.08em] text-zinc-600">
                        Действия
                      </th>
                    </tr>
                  </thead>

                  <tbody>
                    {items.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="px-3 py-2 text-[13px] text-zinc-600">
                          {loading ? "Загрузка..." : "Записи не найдены."}
                        </td>
                      </tr>
                    ) : (
                      items.map((item) => (
                        <tr key={item.contact_id} className="border-t border-zinc-200 align-middle">
                          <td className="px-3 py-1 text-[13px] leading-4 text-zinc-900">
                            {item.contact_id}
                          </td>

                          <td className="px-3 py-1 text-[13px] leading-4 text-zinc-900">
                            {String(item.full_name ?? "").trim() || "—"}
                          </td>

                          <td className="px-3 py-1 text-[13px] leading-4 text-zinc-700">
                            {item.person_id != null ? item.person_id : "—"}
                          </td>

                          <td className="px-3 py-1 text-[13px] leading-4 text-zinc-700">
                            {String(item.phone ?? "").trim() || "—"}
                          </td>

                          <td className="px-3 py-1 text-[13px] leading-4 text-zinc-700">
                            {formatTelegramUsername(item.telegram_username)}
                          </td>

                          <td className="px-3 py-1 text-[13px] leading-4 text-zinc-700">
                            {item.telegram_numeric_id != null ? item.telegram_numeric_id : "—"}
                          </td>

                          <td className="px-3 py-1">
                            <div className="flex items-center gap-1">
                              <button
                                type="button"
                                onClick={() => openEdit(item)}
                                className="rounded-md border border-zinc-200 bg-zinc-100 px-2 py-0.5 text-[10px] leading-4 text-zinc-900 transition hover:bg-zinc-200"
                              >
                                Изменить
                              </button>

                              <button
                                type="button"
                                onClick={() => void handleDelete(item)}
                                className="rounded-md border border-red-300 bg-transparent px-2 py-0.5 text-[10px] leading-4 text-red-700 transition hover:bg-red-50"
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

              <div className="flex items-center justify-between border-t border-zinc-200 px-3 py-2 text-sm">
                <div className="text-zinc-600">
                  Страница {page} из {pages}
                </div>

                <div className="flex gap-2">
                  <button
                    type="button"
                    className="rounded border border-zinc-200 bg-zinc-100 px-3 py-1 text-zinc-800 transition hover:bg-zinc-200 disabled:opacity-50"
                    disabled={offset <= 0 || loading}
                    onClick={() => setOffset((prev) => Math.max(0, prev - PAGE_SIZE))}
                  >
                    Назад
                  </button>

                  <button
                    type="button"
                    className="rounded border border-zinc-200 bg-zinc-100 px-3 py-1 text-zinc-800 transition hover:bg-zinc-200 disabled:opacity-50"
                    disabled={offset + PAGE_SIZE >= total || loading}
                    onClick={() => setOffset((prev) => prev + PAGE_SIZE)}
                  >
                    Вперёд
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <ContactDrawer
        open={drawerOpen}
        mode={drawerMode}
        initialValues={toFormValues(selectedItem)}
        currentItem={selectedItem}
        saving={saving}
        error={drawerError}
        onClose={closeDrawer}
        onSubmit={handleSubmit}
      />
    </div>
  );
}