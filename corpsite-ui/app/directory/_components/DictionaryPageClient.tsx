// FILE: corpsite-ui/app/directory/_components/DictionaryPageClient.tsx
"use client";

import * as React from "react";
import { apiFetchJson } from "@/lib/api";
import type { DictionaryConfig, DictionaryField, DictionaryColumn } from "../_lib/dictionaries.config";

type Props = {
  config: DictionaryConfig;
};

type DictListResponse =
  | {
      items?: Record<string, any>[];
      total?: number;
    }
  | Record<string, any>[];

type DictMutationResponse =
  | {
      item?: Record<string, any>;
      items?: Record<string, any>[];
      data?: Record<string, any>;
      ok?: boolean;
    }
  | Record<string, any>;

type SelectOption = {
  value: string;
  label: string;
};

function normalizeListPayload(payload: DictListResponse): Record<string, any>[] {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.items)) return payload.items;
  return [];
}

function normalizeMutationItem(payload: DictMutationResponse | null | undefined): Record<string, any> | null {
  if (!payload || Array.isArray(payload)) return null;
  if (payload && typeof payload === "object" && payload.item && typeof payload.item === "object") {
    return payload.item;
  }
  if (payload && typeof payload === "object" && payload.data && typeof payload.data === "object") {
    return payload.data;
  }
  if (payload && typeof payload === "object") {
    return payload as Record<string, any>;
  }
  return null;
}

function errorToText(err: any): string {
  if (!err) return "Неизвестная ошибка.";

  if (typeof err === "string") return err;

  if (typeof err?.message === "string" && err.message.trim()) {
    return err.message.trim();
  }

  if (typeof err?.detail === "string" && err.detail.trim()) {
    return err.detail.trim();
  }

  if (Array.isArray(err?.detail)) {
    return err.detail
      .map((x: any) => {
        if (typeof x === "string") return x;
        if (typeof x?.msg === "string" && x.msg.trim()) {
          const loc = Array.isArray(x?.loc) ? x.loc.join(" → ") : "";
          return loc ? `${loc}: ${x.msg}` : x.msg;
        }
        try {
          return JSON.stringify(x);
        } catch {
          return String(x);
        }
      })
      .join("; ");
  }

  if (Array.isArray(err)) {
    return err
      .map((x: any) => {
        if (typeof x === "string") return x;
        try {
          return JSON.stringify(x);
        } catch {
          return String(x);
        }
      })
      .join("; ");
  }

  try {
    return JSON.stringify(err);
  } catch {
    return "Ошибка запроса.";
  }
}

function buildInitialForm(fields: DictionaryField[], source?: Record<string, any> | null) {
  const out: Record<string, any> = {};
  for (const field of fields) {
    if (field.type === "checkbox") {
      out[field.key] = Boolean(source?.[field.key]);
    } else {
      out[field.key] = source?.[field.key] ?? "";
    }
  }
  return out;
}

function formatCellValue(row: Record<string, any>, column: DictionaryColumn): string {
  const rawValue = row[column.key];

  if (column.format === "boolean") {
    return rawValue === true ? "Да" : rawValue === false ? "Нет" : "";
  }

  if (column.key === "name") {
    return String(row.name_ru ?? row.name ?? "");
  }

  if (column.key === "parent_unit_id") {
    return String(rawValue ?? "");
  }

  if (column.key === "group_id") {
    return String(rawValue ?? "");
  }

  return String(rawValue ?? "");
}

function getRowKey(row: Record<string, any>, config: DictionaryConfig, index: number): string {
  const directId = row?.[config.idField];
  if (directId !== undefined && directId !== null && String(directId).trim() !== "") {
    return String(directId);
  }

  const fallback =
    row?.unit_id ??
    row?.role_id ??
    row?.group_id ??
    row?.id ??
    row?.code ??
    `row-${index}`;

  return String(fallback);
}

function getEntityId(row: Record<string, any> | null | undefined, config: DictionaryConfig): string {
  if (!row) return "";
  const raw =
    row?.[config.idField] ??
    row?.unit_id ??
    row?.role_id ??
    row?.group_id ??
    row?.id ??
    row?.code ??
    "";
  return String(raw ?? "").trim();
}

function upsertRow(
  current: Record<string, any>[],
  nextRow: Record<string, any>,
  config: DictionaryConfig
): Record<string, any>[] {
  const nextId = getEntityId(nextRow, config);
  if (!nextId) return current;

  const idx = current.findIndex((row) => getEntityId(row, config) === nextId);
  if (idx < 0) {
    return [nextRow, ...current];
  }

  const copy = [...current];
  copy[idx] = { ...copy[idx], ...nextRow };
  return copy;
}

function removeRow(
  current: Record<string, any>[],
  rowToDelete: Record<string, any>,
  config: DictionaryConfig
): Record<string, any>[] {
  const targetId = getEntityId(rowToDelete, config);
  if (!targetId) return current;
  return current.filter((row) => getEntityId(row, config) !== targetId);
}

function toNullableNumber(value: any): number | null {
  if (value === null || value === undefined) return null;
  const s = String(value).trim();
  if (!s) return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

function isOrgUnitsConfig(config: DictionaryConfig): boolean {
  return config.code === "org-units";
}

function shouldHideField(config: DictionaryConfig, field: DictionaryField): boolean {
  if (isOrgUnitsConfig(config) && field.key === "name_ru") return true;
  return false;
}

function labelForOrgUnit(row: Record<string, any>): string {
  const name = String(row?.name_ru ?? row?.name ?? row?.title ?? "").trim();
  const code = String(row?.code ?? "").trim();
  if (name && code) return `${name} (${code})`;
  return name || code || String(row?.unit_id ?? row?.id ?? "");
}

function labelForDepartmentGroup(row: Record<string, any>): string {
  const name = String(row?.group_name ?? row?.name_ru ?? row?.name ?? "").trim();
  const code = String(row?.code ?? "").trim();
  if (name && code) return `${name} (${code})`;
  return name || code || String(row?.group_id ?? row?.id ?? "");
}

function sanitizePayload(config: DictionaryConfig, form: Record<string, any>, isEdit: boolean, currentId: any) {
  const payload: Record<string, any> = {};

  for (const field of config.formFields) {
    const raw = form[field.key];

    if (field.type === "checkbox") {
      payload[field.key] = Boolean(raw);
      continue;
    }

    const value = typeof raw === "string" ? raw.trim() : raw;
    payload[field.key] = value;
  }

  if (isOrgUnitsConfig(config)) {
    payload.parent_unit_id = toNullableNumber(form.parent_unit_id);
    payload.group_id = toNullableNumber(form.group_id);

    if (isEdit) {
      const currentNumericId = toNullableNumber(currentId);
      if (currentNumericId !== null && payload.parent_unit_id === currentNumericId) {
        payload.parent_unit_id = null;
      }
    }

    delete payload.name_ru;
  }

  return payload;
}

export default function DictionaryPageClient({ config }: Props) {
  const [items, setItems] = React.useState<Record<string, any>[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const [query, setQuery] = React.useState("");
  const [showActiveOnly, setShowActiveOnly] = React.useState(false);

  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [saving, setSaving] = React.useState(false);
  const [editingItem, setEditingItem] = React.useState<Record<string, any> | null>(null);
  const [form, setForm] = React.useState<Record<string, any>>(buildInitialForm(config.formFields));

  const [parentOptions, setParentOptions] = React.useState<SelectOption[]>([]);
  const [groupOptions, setGroupOptions] = React.useState<SelectOption[]>([]);

  const filteredItems = React.useMemo(() => {
    const q = query.trim().toLowerCase();

    return items.filter((row) => {
      const activePass = !showActiveOnly || row.is_active === true;
      if (!activePass) return false;
      if (!q) return true;

      return Object.values(row).some((value) => String(value ?? "").toLowerCase().includes(q));
    });
  }, [items, query, showActiveOnly]);

  const loadItems = React.useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const payload = await apiFetchJson<DictListResponse>(config.apiBase);
      setItems(normalizeListPayload(payload));
    } catch (e: any) {
      setError(errorToText(e));
    } finally {
      setLoading(false);
    }
  }, [config.apiBase]);

  const loadReferenceOptions = React.useCallback(async () => {
    if (!isOrgUnitsConfig(config)) return;

    try {
      const [orgUnitsPayload, groupsPayload] = await Promise.all([
        apiFetchJson<DictListResponse>("/directory/org-units"),
        apiFetchJson<DictListResponse>("/directory/department-groups"),
      ]);

      const orgUnits = normalizeListPayload(orgUnitsPayload);
      const groups = normalizeListPayload(groupsPayload);

      setParentOptions(
        orgUnits
          .map((row) => ({
            value: String(row?.unit_id ?? row?.id ?? "").trim(),
            label: labelForOrgUnit(row),
          }))
          .filter((x) => x.value && x.label)
      );

      setGroupOptions(
        groups
          .map((row) => ({
            value: String(row?.group_id ?? row?.id ?? "").trim(),
            label: labelForDepartmentGroup(row),
          }))
          .filter((x) => x.value && x.label)
      );
    } catch {
      setParentOptions([]);
      setGroupOptions([]);
    }
  }, [config]);

  React.useEffect(() => {
    void loadItems();
    void loadReferenceOptions();
  }, [loadItems, loadReferenceOptions]);

  function openCreate() {
    setEditingItem(null);
    setForm(buildInitialForm(config.formFields));
    setError(null);
    setDrawerOpen(true);
  }

  function openEdit(item: Record<string, any>) {
    setEditingItem(item);
    setForm(buildInitialForm(config.formFields, item));
    setError(null);
    setDrawerOpen(true);
  }

  function closeDrawer() {
    if (saving) return;
    setDrawerOpen(false);
    setEditingItem(null);
    setForm(buildInitialForm(config.formFields));
  }

  function forceCloseDrawer() {
    setDrawerOpen(false);
    setEditingItem(null);
    setForm(buildInitialForm(config.formFields));
  }

  function onChangeField(key: string, value: any) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);

    const isEdit = Boolean(editingItem);
    const id =
      editingItem?.[config.idField] ??
      editingItem?.unit_id ??
      editingItem?.role_id ??
      editingItem?.group_id ??
      editingItem?.id;

    const payload = sanitizePayload(config, form, isEdit, id);

    try {
      const response = await apiFetchJson<DictMutationResponse>(isEdit ? `${config.apiBase}/${id}` : config.apiBase, {
        method: isEdit ? "PATCH" : "POST",
        body: payload,
      });

      const savedItem = normalizeMutationItem(response);

      if (savedItem) {
        setItems((prev) => upsertRow(prev, savedItem, config));
      } else if (isEdit && editingItem) {
        setItems((prev) => upsertRow(prev, { ...editingItem, ...payload }, config));
      } else {
        setItems((prev) => [
          {
            ...payload,
            ...response,
          },
          ...prev,
        ]);
      }

      forceCloseDrawer();

      try {
        await loadItems();
        await loadReferenceOptions();
      } catch {
        setError("Запись сохранена, но список не удалось обновить автоматически.");
      }
    } catch (e: any) {
      setError(errorToText(e));
    } finally {
      setSaving(false);
    }
  }

  async function onDelete(item: Record<string, any>) {
    const id =
      item?.[config.idField] ??
      item?.unit_id ??
      item?.role_id ??
      item?.group_id ??
      item?.id;

    if (!id) return;

    const caption = item.name_ru || item.name || item.group_name || item.code || id;
    const ok = window.confirm(`Удалить запись "${caption}"?`);
    if (!ok) return;

    setError(null);

    try {
      await apiFetchJson(`${config.apiBase}/${id}`, { method: "DELETE" });
      setItems((prev) => removeRow(prev, item, config));

      try {
        await loadItems();
        await loadReferenceOptions();
      } catch {
        setError("Запись удалена, но список не удалось обновить автоматически.");
      }
    } catch (e: any) {
      setError(errorToText(e));
    }
  }

  const visibleFormFields = React.useMemo(
    () => config.formFields.filter((field) => !shouldHideField(config, field)),
    [config]
  );

  const availableParentOptions = React.useMemo(() => {
    const currentId = String(editingItem?.[config.idField] ?? editingItem?.unit_id ?? editingItem?.id ?? "").trim();
    if (!currentId) return parentOptions;
    return parentOptions.filter((item) => item.value !== currentId);
  }, [parentOptions, editingItem, config]);

  return (
    <div className="relative rounded-2xl border border-zinc-800 bg-zinc-900/40 text-zinc-100">
      <div className="space-y-6 p-6">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{config.title}</h1>
        </div>

        <div className="flex flex-col gap-3 rounded-2xl border border-zinc-800 bg-zinc-950/40 p-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-1 flex-col gap-3 md:flex-row">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={config.searchPlaceholder}
              className="w-full rounded-xl border border-zinc-700 bg-zinc-950 px-4 py-2.5 text-sm outline-none placeholder:text-zinc-500 focus:border-zinc-500 md:max-w-xl"
            />

            <label className="inline-flex items-center gap-2 rounded-xl border border-zinc-700 bg-zinc-950 px-4 py-2.5 text-sm text-zinc-300">
              <input
                type="checkbox"
                checked={showActiveOnly}
                onChange={(e) => setShowActiveOnly(e.target.checked)}
                className="h-4 w-4"
              />
              Только активные
            </label>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => {
                setQuery("");
                setShowActiveOnly(false);
                void loadItems();
              }}
              className="rounded-xl border border-zinc-700 px-4 py-2.5 text-sm font-medium text-zinc-200 transition hover:bg-zinc-800"
            >
              Обновить
            </button>

            <button
              type="button"
              onClick={openCreate}
              className="rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-blue-500"
            >
              Создать
            </button>
          </div>
        </div>

        {error ? (
          <div className="rounded-2xl border border-red-900/60 bg-red-950/40 px-4 py-3 text-sm text-red-200">
            {error}
          </div>
        ) : null}

        <div className="overflow-hidden rounded-2xl border border-zinc-800 bg-zinc-950/30">
          <div className="overflow-x-auto">
            <table className="min-w-full border-collapse">
              <thead className="bg-zinc-900/80">
                <tr className="border-b border-zinc-800">
                  {config.columns.map((column) => (
                    <th
                      key={column.key}
                      className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-zinc-400"
                      style={column.width ? { width: column.width } : undefined}
                    >
                      {column.title}
                    </th>
                  ))}
                  <th className="w-[180px] px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-zinc-400">
                    Действия
                  </th>
                </tr>
              </thead>

              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan={config.columns.length + 1} className="px-4 py-10 text-center text-sm text-zinc-400">
                      Загрузка...
                    </td>
                  </tr>
                ) : filteredItems.length === 0 ? (
                  <tr>
                    <td colSpan={config.columns.length + 1} className="px-4 py-10 text-center text-sm text-zinc-500">
                      Нет данных
                    </td>
                  </tr>
                ) : (
                  filteredItems.map((row, index) => {
                    const rowKey = getRowKey(row, config, index);

                    return (
                      <tr key={rowKey} className="border-b border-zinc-800/80 last:border-b-0">
                        {config.columns.map((column) => {
                          const value = formatCellValue(row, column);

                          return (
                            <td key={`${rowKey}-${column.key}`} className="px-4 py-3 text-sm text-zinc-200">
                              {value}
                            </td>
                          );
                        })}

                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              onClick={() => openEdit(row)}
                              className="rounded-lg border border-zinc-700 px-3 py-1.5 text-xs font-medium text-zinc-200 transition hover:bg-zinc-800"
                            >
                              Изменить
                            </button>

                            <button
                              type="button"
                              onClick={() => void onDelete(row)}
                              className="rounded-lg border border-red-900/70 px-3 py-1.5 text-xs font-medium text-red-300 transition hover:bg-red-950/40"
                            >
                              Удалить
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {drawerOpen ? (
        <>
          <div className="fixed inset-0 z-40 bg-black/50" onClick={closeDrawer} />
          <div className="fixed right-0 top-0 z-50 h-full w-full max-w-xl border-l border-zinc-800 bg-zinc-950 shadow-2xl">
            <div className="flex h-full flex-col">
              <div className="flex items-center justify-between border-b border-zinc-800 px-6 py-4">
                <div>
                  <h2 className="text-lg font-semibold text-zinc-100">
                    {editingItem ? "Редактирование записи" : "Создание записи"}
                  </h2>
                  <p className="mt-1 text-sm text-zinc-400">{config.title}</p>
                </div>

                <button
                  type="button"
                  onClick={closeDrawer}
                  disabled={saving}
                  className="rounded-lg border border-zinc-700 px-3 py-2 text-sm text-zinc-300 transition hover:bg-zinc-900 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Закрыть
                </button>
              </div>

              <form onSubmit={onSubmit} className="flex min-h-0 flex-1 flex-col">
                <div className="flex-1 space-y-5 overflow-y-auto px-6 py-5">
                  {visibleFormFields.map((field) => {
                    if (field.type === "checkbox") {
                      return (
                        <label key={field.key} className="flex items-center gap-3 text-sm text-zinc-200">
                          <input
                            type="checkbox"
                            checked={Boolean(form[field.key])}
                            onChange={(e) => onChangeField(field.key, e.target.checked)}
                            className="h-4 w-4"
                          />
                          {field.label}
                        </label>
                      );
                    }

                    if (field.type === "textarea") {
                      return (
                        <div key={field.key} className="space-y-2">
                          <label className="block text-sm font-medium text-zinc-300">
                            {field.label}
                            {field.required ? <span className="ml-1 text-red-400">*</span> : null}
                          </label>
                          <textarea
                            value={form[field.key] ?? ""}
                            onChange={(e) => onChangeField(field.key, e.target.value)}
                            placeholder={field.placeholder}
                            rows={4}
                            className="w-full rounded-xl border border-zinc-700 bg-zinc-900 px-4 py-3 text-sm text-zinc-100 outline-none placeholder:text-zinc-500 focus:border-zinc-500"
                          />
                        </div>
                      );
                    }

                    if (isOrgUnitsConfig(config) && field.key === "parent_unit_id") {
                      return (
                        <div key={field.key} className="space-y-2">
                          <label className="block text-sm font-medium text-zinc-300">{field.label}</label>
                          <select
                            value={String(form[field.key] ?? "")}
                            onChange={(e) => onChangeField(field.key, e.target.value)}
                            className="w-full rounded-xl border border-zinc-700 bg-zinc-900 px-4 py-3 text-sm text-zinc-100 outline-none focus:border-zinc-500"
                          >
                            <option value="">Не выбрано</option>
                            {availableParentOptions.map((option) => (
                              <option key={option.value} value={option.value}>
                                {option.label}
                              </option>
                            ))}
                          </select>
                        </div>
                      );
                    }

                    if (isOrgUnitsConfig(config) && field.key === "group_id") {
                      return (
                        <div key={field.key} className="space-y-2">
                          <label className="block text-sm font-medium text-zinc-300">{field.label}</label>
                          <select
                            value={String(form[field.key] ?? "")}
                            onChange={(e) => onChangeField(field.key, e.target.value)}
                            className="w-full rounded-xl border border-zinc-700 bg-zinc-900 px-4 py-3 text-sm text-zinc-100 outline-none focus:border-zinc-500"
                          >
                            <option value="">Не выбрано</option>
                            {groupOptions.map((option) => (
                              <option key={option.value} value={option.value}>
                                {option.label}
                              </option>
                            ))}
                          </select>
                        </div>
                      );
                    }

                    return (
                      <div key={field.key} className="space-y-2">
                        <label className="block text-sm font-medium text-zinc-300">
                          {field.label}
                          {field.required ? <span className="ml-1 text-red-400">*</span> : null}
                        </label>
                        <input
                          value={form[field.key] ?? ""}
                          onChange={(e) => onChangeField(field.key, e.target.value)}
                          placeholder={field.placeholder}
                          className="w-full rounded-xl border border-zinc-700 bg-zinc-900 px-4 py-3 text-sm text-zinc-100 outline-none placeholder:text-zinc-500 focus:border-zinc-500"
                        />
                      </div>
                    );
                  })}
                </div>

                <div className="sticky bottom-0 flex items-center justify-end gap-3 border-t border-zinc-800 bg-zinc-950 px-6 py-4">
                  <button
                    type="button"
                    onClick={closeDrawer}
                    disabled={saving}
                    className="rounded-xl border border-zinc-700 px-4 py-2.5 text-sm font-medium text-zinc-200 transition hover:bg-zinc-900 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    Отмена
                  </button>

                  <button
                    type="submit"
                    disabled={saving}
                    className="rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {saving ? "Сохранение..." : "Сохранить"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}