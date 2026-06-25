// FILE: corpsite-ui/app/directory/contacts/page.tsx
"use client";

import * as React from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import OrgScopeFilter from "@/components/OrgScopeFilter";
import OrgUnitScopeFilter from "@/components/OrgUnitScopeFilter";
import { apiFetchJson } from "@/lib/api";
import { formatThrownError, uiFieldLabel } from "@/lib/i18n";
import { ORG_GROUP_ID_PARAM, readOrgScopeFromSearchParams } from "@/lib/orgScope";

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
  telegram_numeric_id: string;
};

type PositionSlot = {
  position_id: number;
  name: string;
};

type WorkingExpertRow = {
  user_id: number;
  full_name?: string | null;
  role_name?: string | null;
  role_name_ru?: string | null;
  phone?: string | null;
  telegram_username?: string | null;
  telegram_id?: number | null;
  unit_name?: string | null;
};

type ContactDisplayRow =
  | { kind: "contact"; item: ContactItem }
  | { kind: "expert"; item: WorkingExpertRow }
  | { kind: "slot"; position_id: number; slot_label: string };

const POSITIONS_API = "/directory/positions";
const WORKING_CONTACTS_API = "/directory/working-contacts";
const API_BASE = "/directory/contacts";
const PAGE_SIZE = 100;
const ORG_FILTER_PARAM_KEYS = [
  ORG_GROUP_ID_PARAM,
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
  return formatThrownError(error, { fallback: "Не удалось выполнить операцию." });
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

function normalizeLabel(value?: string | null): string {
  return String(value ?? "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .replace(/[ё]/g, "е")
    .trim();
}

function normalizePositionItems(payload: unknown): PositionSlot[] {
  const body = payload as { items?: Array<{ position_id?: number; id?: number; name?: string }> };
  const items = Array.isArray(body?.items) ? body.items : [];
  return items
    .map((row) => ({
      position_id: Number(row.position_id ?? row.id ?? 0),
      name: String(row.name ?? "").trim(),
    }))
    .filter((row) => Number.isFinite(row.position_id) && row.position_id > 0 && row.name);
}

function normalizeWorkingExperts(payload: unknown): WorkingExpertRow[] {
  const body = payload as { items?: WorkingExpertRow[] };
  const items = Array.isArray(body?.items) ? body.items : [];
  return items.filter((row) => {
    const role = normalizeLabel(row.role_name_ru ?? row.role_name);
    return role.includes("эксперт");
  });
}

function contactCoversLabel(contacts: ContactItem[], label: string): boolean {
  const target = normalizeLabel(label);
  if (!target) return false;

  return contacts.some((contact) => {
    const fullName = normalizeLabel(contact.full_name);
    return fullName === target || fullName.includes(target) || target.includes(fullName);
  });
}

function buildDisplayRows(
  contacts: ContactItem[],
  positions: PositionSlot[],
  experts: WorkingExpertRow[],
): ContactDisplayRow[] {
  const rows: ContactDisplayRow[] = contacts.map((item) => ({ kind: "contact", item }));

  for (const expert of experts) {
    const roleLabel = String(expert.role_name_ru ?? expert.role_name ?? expert.full_name ?? "").trim();
    if (!roleLabel || contactCoversLabel(contacts, roleLabel)) continue;

    rows.push({ kind: "expert", item: expert });
  }

  for (const position of positions) {
    if (contactCoversLabel(contacts, position.name)) continue;
    rows.push({ kind: "slot", position_id: position.position_id, slot_label: position.name });
  }

  return rows;
}

function formatTelegramId(value?: number | null): string {
  return value != null && Number.isFinite(value) ? String(value) : "—";
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
      telegram_numeric_id: values.telegram_numeric_id.trim(),
    });
  }

  return (
    <div className="fixed inset-0 z-50 flex">
      <div
        className="absolute inset-0 bg-zinc-600/35 dark:bg-black/50 backdrop-blur-sm"
        onClick={saving ? undefined : onClose}
      />
      <div className="relative ml-auto flex h-full w-full max-w-[760px] flex-col border-l border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 shadow-2xl">
        <form onSubmit={handleSubmit} className="flex h-full flex-col bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50">
          <div className="flex items-start justify-between border-b border-zinc-200 dark:border-zinc-800 px-6 py-5">
            <div>
              <h2 className="text-2xl font-semibold leading-tight text-zinc-900 dark:text-zinc-50">
                {mode === "create" ? "Создание контакта" : "Редактирование контакта"}
              </h2>
              <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">Справочник контактов</p>
            </div>

            <button
              type="button"
              onClick={onClose}
              disabled={saving}
              className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700 disabled:opacity-60"
            >
              Закрыть
            </button>
          </div>

          <div className="flex-1 overflow-y-auto px-6 py-5">
            <div className="mx-auto flex w-full max-w-3xl flex-col gap-5">
              {!!error && (
                <div className="rounded-xl border border-red-200 dark:border-red-900/55 bg-red-50 dark:bg-red-950/35 px-4 py-3 text-sm text-red-800 dark:text-red-200">
                  {error}
                </div>
              )}

              {mode === "edit" && currentItem ? (
                <div className="grid grid-cols-1 gap-3 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4 text-sm text-zinc-700 dark:text-zinc-300 md:grid-cols-2">
                  <div>
                    <div className="text-xs uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">ID</div>
                    <div className="mt-1 text-zinc-900 dark:text-zinc-50">{currentItem.contact_id}</div>
                  </div>
                  <div>
                    <div className="text-xs uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">
                      {uiFieldLabel("person_id")}
                    </div>
                    <div className="mt-1 text-zinc-900 dark:text-zinc-50">
                      {currentItem.person_id != null ? currentItem.person_id : "—"}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">Создан</div>
                    <div className="mt-1 text-zinc-900 dark:text-zinc-50">{formatDateTime(currentItem.created_at)}</div>
                  </div>
                  <div>
                    <div className="text-xs uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">Обновлён</div>
                    <div className="mt-1 text-zinc-900 dark:text-zinc-50">{formatDateTime(currentItem.updated_at)}</div>
                  </div>
                </div>
              ) : null}

              <div className="flex flex-col gap-2">
                <label htmlFor="full_name" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
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
                  className="h-11 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400"
                  required
                />
              </div>

              <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                <div className="flex flex-col gap-2">
                  <label htmlFor="person_id" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
                    {uiFieldLabel("person_id")}
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
                    className="h-11 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400"
                  />
                </div>

                <div className="flex flex-col gap-2">
                  <label htmlFor="phone" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
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
                    className="h-11 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400"
                  />
                </div>
              </div>

              <div className="flex flex-col gap-2">
                <label htmlFor="telegram_numeric_id" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
                  Telegram ID
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
                  placeholder="Например: 7685102887"
                  autoComplete="off"
                  spellCheck={false}
                  className="h-11 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400"
                />
                <p className="text-xs text-zinc-500 dark:text-zinc-400">
                  Основной технический идентификатор для Telegram-бота.
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center justify-end gap-3 border-t border-zinc-200 dark:border-zinc-800 px-6 py-4">
            <button
              type="button"
              onClick={onClose}
              disabled={saving}
              className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700 disabled:opacity-60"
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

  const orgScope = React.useMemo(() => readOrgScopeFromSearchParams(sp), [sp]);
  const orgGroupId = orgScope.org_group_id;
  const orgUnitId = React.useMemo(() => readSelectedOrgUnitId(sp), [sp]);
  const orgUnitNameFromUrl = React.useMemo(() => {
    const v = String(sp.get("org_unit_name") ?? "").trim();
    return v || null;
  }, [sp]);

  const [items, setItems] = React.useState<ContactItem[]>([]);
  const [displayRows, setDisplayRows] = React.useState<ContactDisplayRow[]>([]);
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
  const [createPresetName, setCreatePresetName] = React.useState("");

  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const pages = Math.max(1, Math.ceil(Math.max(total, 1) / PAGE_SIZE));

  React.useEffect(() => {
    setOffset(0);
  }, [orgGroupId, orgUnitId]);

  const loadItems = React.useCallback(async () => {
    setLoading(true);
    setPageError(null);

    try {
      const scopeQuery = {
        org_group_id: orgGroupId ?? undefined,
        org_unit_id: orgUnitId ?? undefined,
      };

      const [data, positionsPayload, workingPayload] = await Promise.all([
        apiFetchJson<ContactsResponse>(API_BASE, {
          query: {
            q: appliedSearch || undefined,
            ...scopeQuery,
            limit: PAGE_SIZE,
            offset,
          },
        }),
        apiFetchJson(POSITIONS_API, {
          query: {
            ...scopeQuery,
            limit: 200,
            offset: 0,
          },
        }).catch(() => ({ items: [] })),
        apiFetchJson(WORKING_CONTACTS_API, {
          query: {
            ...scopeQuery,
            active_only: true,
            limit: 200,
            offset: 0,
          },
        }).catch(() => ({ items: [] })),
      ]);

      const normalized = normalizeItems(data);
      const positions = normalizePositionItems(positionsPayload);
      const experts = normalizeWorkingExperts(workingPayload);
      const rows = buildDisplayRows(normalized, positions, experts);

      setItems(normalized);
      setDisplayRows(rows);
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
      setDisplayRows([]);
      setTotal(0);
      setFilterOrgUnitId(null);
      setFilterOrgUnitName(null);
    } finally {
      setLoading(false);
    }
  }, [appliedSearch, orgGroupId, orgUnitId, offset, refreshNonce]);

  React.useEffect(() => {
    void loadItems();
  }, [loadItems]);

  function openCreate(presetName = "") {
    setDrawerError(null);
    setSelectedItem(null);
    setCreatePresetName(String(presetName || "").trim());
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
    setCreatePresetName("");
  }

  async function handleSubmit(values: ContactFormValues) {
    setSaving(true);
    setDrawerError(null);

    try {
      const personId = parseOptionalPositiveInt(values.person_id);
      if (values.person_id.trim() && personId === null) {
        throw new Error(`${uiFieldLabel("person_id")} должен быть положительным целым числом.`);
      }

      const telegramNumericId = parseOptionalPositiveInt(values.telegram_numeric_id);
      if (values.telegram_numeric_id.trim() && telegramNumericId === null) {
        throw new Error("telegram_numeric_id должен быть положительным целым числом.");
      }

      const preservedUsername =
        drawerMode === "edit" && selectedItem?.telegram_username
          ? String(selectedItem.telegram_username).trim() || null
          : null;

      const payload = {
        full_name: values.full_name.trim(),
        person_id: personId,
        phone: values.phone.trim() || null,
        telegram_username: preservedUsername,
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
    <div className="bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50">
      <div className="mx-auto w-full max-w-[1440px] px-4 py-3">
        <div className="overflow-hidden rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950">
          <div className="border-b border-zinc-200 dark:border-zinc-800 px-4 py-3">
            <h1 className="text-xl font-semibold leading-none text-zinc-900 dark:text-zinc-50">
              Контакты{filterCaption ? ` (${filterCaption})` : ""}
            </h1>
          </div>

          <div className="border-b border-zinc-200 dark:border-zinc-800 px-4 py-2">
            <form onSubmit={handleApplySearch} className="flex flex-col gap-2 xl:flex-row xl:items-end">
              <OrgScopeFilter
                basePath="/directory/contacts"
                className="min-w-[240px]"
                resetParamsOnChange={["offset", "org_unit_id", "org_unit_name"]}
              />

              <OrgUnitScopeFilter
                basePath="/directory/contacts"
                className="min-w-[240px]"
                resetParamsOnChange={["offset"]}
              />

              <div className="flex-1">
                <input
                  value={searchDraft}
                  onChange={(e) => setSearchDraft(e.target.value)}
                  placeholder={`Поиск по ID, ${uiFieldLabel("person_id")}, ФИО, телефону, Telegram`}
                  className="h-8.5 w-full rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 py-1 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400"
                />
              </div>

              <button
                type="submit"
                className="h-8.5 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 py-1 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700"
              >
                Найти
              </button>

              <button
                type="button"
                onClick={handleRefresh}
                className="h-8.5 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 py-1 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700"
              >
                Обновить
              </button>

              <button
                type="button"
                onClick={() => openCreate()}
                className="h-8.5 rounded-lg bg-blue-600 px-3.5 py-1 text-sm font-medium text-white transition hover:bg-blue-500"
              >
                Создать
              </button>
            </form>
          </div>

          <div className="px-4 py-2">
            {!!pageError && (
              <div className="mb-2 rounded-xl border border-red-200 dark:border-red-900/55 bg-red-50 dark:bg-red-950/35 px-4 py-2 text-sm text-red-800 dark:text-red-200">
                {pageError}
              </div>
            )}

            <div className="mb-1.5 flex items-center justify-between gap-2 text-[11px] text-zinc-600 dark:text-zinc-400">
              <div>
                Контактов: {total} · Строк в списке: {displayRows.length}
                {displayRows.length > items.length ? (
                  <span className="ml-1">· включая пустые слоты</span>
                ) : null}
              </div>
              <div>
                Страница {page} из {pages}
                {loading ? " (обновление...)" : ""}
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
                      <th className="min-w-[280px] px-3 py-1 text-[10px] font-medium uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">
                        ФИО
                      </th>
                      <th className="min-w-[120px] px-3 py-1 text-[10px] font-medium uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">
                        {uiFieldLabel("person_id")}
                      </th>
                      <th className="min-w-[180px] px-3 py-1 text-[10px] font-medium uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">
                        Телефон
                      </th>
                      <th className="min-w-[180px] px-3 py-1 text-[10px] font-medium uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">
                        Telegram ID
                      </th>
                      <th className="w-[190px] px-3 py-1 text-[10px] font-medium uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">
                        Действия
                      </th>
                    </tr>
                  </thead>

                  <tbody>
                    {displayRows.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="px-3 py-2 text-[13px] text-zinc-600 dark:text-zinc-400">
                          {loading ? (
                            "Загрузка..."
                          ) : appliedSearch ? (
                            <span>
                              Записи не найдены в операционном контуре задач. Если человек есть только в
                              кадровом импорте, откройте{" "}
                              <a
                                href="/directory/personnel/import/normalized-records"
                                className="text-blue-600 underline underline-offset-2 hover:text-blue-500 dark:text-blue-400"
                              >
                                «Кадровые процессы → Импорт»
                              </a>{" "}
                              и выполните enrollment («Добавить в персонал» / зачисление в operational).
                            </span>
                          ) : (
                            "Записи не найдены."
                          )}
                        </td>
                      </tr>
                    ) : (
                      displayRows.map((row) => {
                        if (row.kind === "contact") {
                          const item = row.item;
                          return (
                            <tr
                              key={`contact-${item.contact_id}`}
                              className="border-t border-zinc-200 dark:border-zinc-800 align-middle"
                            >
                              <td className="px-3 py-1 text-[13px] leading-4 text-zinc-900 dark:text-zinc-50">
                                {item.contact_id}
                              </td>

                              <td className="px-3 py-1 text-[13px] leading-4 text-zinc-900 dark:text-zinc-50">
                                {String(item.full_name ?? "").trim() || "—"}
                              </td>

                              <td className="px-3 py-1 text-[13px] leading-4 text-zinc-700 dark:text-zinc-300">
                                {item.person_id != null ? item.person_id : "—"}
                              </td>

                              <td className="px-3 py-1 text-[13px] leading-4 text-zinc-700 dark:text-zinc-300">
                                {String(item.phone ?? "").trim() || "—"}
                              </td>

                              <td className="px-3 py-1 text-[13px] leading-4 text-zinc-700 dark:text-zinc-300">
                                {formatTelegramId(item.telegram_numeric_id)}
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
                          );
                        }

                        if (row.kind === "expert") {
                          const item = row.item;
                          const roleLabel = String(item.role_name_ru ?? item.role_name ?? "").trim();
                          return (
                            <tr
                              key={`expert-${item.user_id}`}
                              className="border-t border-zinc-200 dark:border-zinc-800 align-middle bg-blue-50/40 dark:bg-blue-950/15"
                            >
                              <td className="px-3 py-1 text-[13px] leading-4 text-zinc-700 dark:text-zinc-300">
                                эксперт
                              </td>
                              <td className="px-3 py-1 text-[13px] leading-4 text-zinc-900 dark:text-zinc-50">
                                <div>{String(item.full_name ?? "").trim() || roleLabel || "—"}</div>
                                {roleLabel ? (
                                  <div className="text-[11px] text-zinc-500 dark:text-zinc-400">{roleLabel}</div>
                                ) : null}
                              </td>
                              <td className="px-3 py-1 text-[13px] leading-4 text-zinc-700 dark:text-zinc-300">—</td>
                              <td className="px-3 py-1 text-[13px] leading-4 text-zinc-700 dark:text-zinc-300">
                                {String(item.phone ?? "").trim() || "—"}
                              </td>
                              <td className="px-3 py-1 text-[13px] leading-4 text-zinc-700 dark:text-zinc-300">
                                {formatTelegramId(item.telegram_id)}
                              </td>
                              <td className="px-3 py-1 text-[11px] text-zinc-500 dark:text-zinc-400">
                                из рабочих контактов
                              </td>
                            </tr>
                          );
                        }

                        return (
                          <tr
                            key={`slot-${row.position_id}`}
                            className="border-t border-zinc-200 dark:border-zinc-800 align-middle bg-zinc-50/70 dark:bg-zinc-900/40"
                          >
                            <td className="px-3 py-1 text-[13px] leading-4 text-zinc-500 dark:text-zinc-400">слот</td>
                            <td className="px-3 py-1 text-[13px] leading-4 text-zinc-700 dark:text-zinc-300">
                              <div>{row.slot_label}</div>
                              <div className="text-[11px] text-zinc-500 dark:text-zinc-400">контакт не заполнен</div>
                            </td>
                            <td className="px-3 py-1 text-[13px] leading-4 text-zinc-500 dark:text-zinc-400">—</td>
                            <td className="px-3 py-1 text-[13px] leading-4 text-zinc-500 dark:text-zinc-400">—</td>
                            <td className="px-3 py-1">
                              <button
                                type="button"
                                onClick={() => openCreate(row.slot_label)}
                                className="rounded-md border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-2 py-0.5 text-[10px] leading-4 text-zinc-900 dark:text-zinc-50 transition hover:bg-zinc-200 dark:hover:bg-zinc-700"
                              >
                                Заполнить
                              </button>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>

              <div className="flex items-center justify-between border-t border-zinc-200 dark:border-zinc-800 px-3 py-2 text-sm">
                <div className="text-zinc-600 dark:text-zinc-400">
                  Страница {page} из {pages}
                </div>

                <div className="flex gap-2">
                  <button
                    type="button"
                    className="rounded border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 py-1 text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700 disabled:opacity-50"
                    disabled={offset <= 0 || loading}
                    onClick={() => setOffset((prev) => Math.max(0, prev - PAGE_SIZE))}
                  >
                    Назад
                  </button>

                  <button
                    type="button"
                    className="rounded border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 py-1 text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700 disabled:opacity-50"
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
        initialValues={{
          ...toFormValues(selectedItem),
          full_name: drawerMode === "create" && createPresetName ? createPresetName : toFormValues(selectedItem).full_name,
        }}
        currentItem={selectedItem}
        saving={saving}
        error={drawerError}
        onClose={closeDrawer}
        onSubmit={handleSubmit}
      />
    </div>
  );
}