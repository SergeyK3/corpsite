"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";
import { apiFetchJson } from "../../../../lib/api";
import RoleDrawer from "./RoleDrawer";
import type { RoleFormValues } from "./RoleForm";

type RoleItem = {
  role_id?: number;
  id?: number;

  role_code?: string;
  role_name?: string;

  code?: string;
  name?: string;
  name_ru?: string | null;

  description?: string | null;
  is_active?: boolean | null;
};

type RolesResponse =
  | RoleItem[]
  | {
      items?: RoleItem[];
      data?: RoleItem[];
      total?: number;
    };

const API_BASE = "/directory/roles";

function roleIdOf(role: RoleItem): number {
  return Number(role.role_id ?? role.id ?? 0);
}

function roleCodeOf(role: RoleItem): string {
  return String(role.role_code ?? role.code ?? "").trim();
}

function roleNameOf(role: RoleItem): string {
  return String(role.role_name ?? role.name ?? "").trim();
}

function normalizeRoles(payload: RolesResponse): RoleItem[] {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload.items)) return payload.items;
  if (Array.isArray(payload.data)) return payload.data;
  return [];
}

function extractErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message) return error.message;
  return "Не удалось выполнить операцию.";
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function parsePositiveInt(value: string | null): number | null {
  const n = Number(String(value ?? "").trim());
  if (!Number.isFinite(n) || n <= 0) return null;
  return Math.trunc(n);
}

function matchesSearch(role: RoleItem, rawQuery: string): boolean {
  const query = rawQuery.trim().toLowerCase();
  if (!query) return true;

  const haystack = [
    roleCodeOf(role),
    roleNameOf(role),
    String(role.name_ru ?? "").trim(),
    String(role.description ?? "").trim(),
  ]
    .join(" ")
    .toLowerCase();

  if (!haystack) return false;
  if (haystack.includes(query)) return true;

  const tokens = query.split(/\s+/).filter(Boolean);
  if (tokens.length > 0 && tokens.every((token) => haystack.includes(token))) {
    return true;
  }

  try {
    const pattern = tokens.map(escapeRegExp).join(".*");
    if (pattern) {
      const re = new RegExp(pattern, "i");
      if (re.test(haystack)) return true;
    }
  } catch {
    // ignore invalid regex construction
  }

  return false;
}

export default function RolesPageClient() {
  const sp = useSearchParams();
  const orgUnitId = React.useMemo(() => parsePositiveInt(sp.get("org_unit_id")), [sp]);

  const [items, setItems] = React.useState<RoleItem[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [saving, setSaving] = React.useState(false);
  const [search, setSearch] = React.useState("");
  const [onlyActive, setOnlyActive] = React.useState(false);
  const [pageError, setPageError] = React.useState<string | null>(null);
  const [drawerError, setDrawerError] = React.useState<string | null>(null);

  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [drawerMode, setDrawerMode] = React.useState<"create" | "edit">("create");
  const [selectedRole, setSelectedRole] = React.useState<RoleItem | null>(null);

  const loadRoles = React.useCallback(async () => {
    setLoading(true);
    setPageError(null);

    try {
      const params = new URLSearchParams();

      if (onlyActive) params.set("is_active", "true");
      if (orgUnitId != null) params.set("org_unit_id", String(orgUnitId));

      const url = params.toString() ? `${API_BASE}?${params.toString()}` : API_BASE;
      const data = await apiFetchJson<RolesResponse>(url);
      const normalized = normalizeRoles(data);

      setItems(normalized);

      if (selectedRole) {
        const selectedId = roleIdOf(selectedRole);
        const stillVisible = normalized.some((role) => roleIdOf(role) === selectedId);
        if (!stillVisible) {
          setDrawerOpen(false);
          setSelectedRole(null);
          setDrawerError(null);
        }
      }
    } catch (error) {
      setPageError(extractErrorMessage(error));
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [onlyActive, orgUnitId, selectedRole]);

  React.useEffect(() => {
    void loadRoles();
  }, [loadRoles]);

  const filteredItems = React.useMemo(() => {
    return items.filter((role) => matchesSearch(role, search));
  }, [items, search]);

  function openCreate() {
    setDrawerError(null);
    setSelectedRole(null);
    setDrawerMode("create");
    setDrawerOpen(true);
  }

  function openEdit(role: RoleItem) {
    setDrawerError(null);
    setSelectedRole(role);
    setDrawerMode("edit");
    setDrawerOpen(true);
  }

  function closeDrawer() {
    if (saving) return;
    setDrawerOpen(false);
    setDrawerError(null);
    setSelectedRole(null);
  }

  async function handleSubmit(values: RoleFormValues) {
    setSaving(true);
    setDrawerError(null);

    const payload = {
      role_code: values.role_code.trim(),
      role_name: values.role_name.trim(),
      description: values.description.trim() || null,
      is_active: !!values.is_active,
    };

    try {
      if (drawerMode === "create") {
        await apiFetchJson(API_BASE, {
          method: "POST",
          body: payload,
        });
      } else {
        const roleId = roleIdOf(selectedRole as RoleItem);
        await apiFetchJson(`${API_BASE}/${roleId}`, {
          method: "PUT",
          body: payload,
        });
      }

      setDrawerOpen(false);
      setSelectedRole(null);
      await loadRoles();
    } catch (error) {
      setDrawerError(extractErrorMessage(error));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(role: RoleItem) {
    const roleId = roleIdOf(role);
    const roleTitle = roleNameOf(role) || roleCodeOf(role);

    const ok = window.confirm(`Удалить роль «${roleTitle}»?`);
    if (!ok) return;

    setPageError(null);

    try {
      await apiFetchJson(`${API_BASE}/${roleId}`, {
        method: "DELETE",
      });
      await loadRoles();
    } catch (error) {
      setPageError(extractErrorMessage(error));
    }
  }

  return (
    <div className="bg-[#04070f] text-zinc-100">
      <div className="mx-auto w-full max-w-[1440px] px-4 py-4">
        <div className="overflow-hidden rounded-2xl border border-zinc-800 bg-[#050816]">
          <div className="border-b border-zinc-800 px-6 py-6">
            <h1 className="text-2xl font-semibold text-zinc-100">Роли</h1>
          </div>

          <div className="border-b border-zinc-800 px-6 py-4">
            <div className="flex flex-col gap-3 xl:flex-row xl:items-center">
              <div className="flex-1">
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Поиск по коду и названию"
                  className="h-12 w-full rounded-lg border border-zinc-800 bg-zinc-950/40 px-4 py-2 text-sm text-zinc-100 outline-none transition placeholder:text-zinc-500 focus:border-zinc-600"
                />
              </div>

              <label className="flex h-12 min-w-[200px] items-center gap-3 rounded-lg border border-zinc-800 bg-zinc-950/40 px-4 py-2 text-sm text-zinc-200">
                <input
                  type="checkbox"
                  checked={onlyActive}
                  onChange={(e) => setOnlyActive(e.target.checked)}
                  className="h-4 w-4 rounded border-zinc-700 bg-zinc-900"
                />
                Только активные
              </label>

              <button
                type="button"
                onClick={() => void loadRoles()}
                className="h-12 rounded-lg border border-zinc-800 bg-zinc-950/40 px-4 py-2 text-sm text-zinc-200 transition hover:bg-zinc-900/60"
              >
                Обновить
              </button>

              <button
                type="button"
                onClick={openCreate}
                className="h-12 rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white transition hover:bg-blue-500"
              >
                Создать
              </button>
            </div>
          </div>

          <div className="px-6 py-4">
            {!!pageError && (
              <div className="mb-4 rounded-xl border border-red-900/60 bg-red-950/40 px-4 py-3 text-sm text-red-200">
                {pageError}
              </div>
            )}

            <div className="mb-3 text-sm text-zinc-400">
              Всего: {items.length} · Показано: {filteredItems.length}
              {orgUnitId != null ? <span className="ml-2">· Оргфильтр: unit #{orgUnitId}</span> : null}
            </div>

            <div className="overflow-hidden rounded-2xl border border-zinc-800">
              <div className="overflow-x-auto">
                <table className="min-w-full border-collapse">
                  <thead>
                    <tr className="bg-white/[0.03] text-left">
                      <th className="px-5 py-4 text-sm font-medium uppercase tracking-[0.08em] text-zinc-400">
                        ID
                      </th>
                      <th className="px-5 py-4 text-sm font-medium uppercase tracking-[0.08em] text-zinc-400">
                        Код роли
                      </th>
                      <th className="px-5 py-4 text-sm font-medium uppercase tracking-[0.08em] text-zinc-400">
                        Название
                      </th>
                      <th className="px-5 py-4 text-sm font-medium uppercase tracking-[0.08em] text-zinc-400">
                        Активна
                      </th>
                      <th className="px-5 py-4 text-sm font-medium uppercase tracking-[0.08em] text-zinc-400">
                        Действия
                      </th>
                    </tr>
                  </thead>

                  <tbody>
                    {loading ? (
                      <tr>
                        <td colSpan={5} className="px-5 py-6 text-sm text-zinc-400">
                          Загрузка...
                        </td>
                      </tr>
                    ) : filteredItems.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="px-5 py-6 text-sm text-zinc-500">
                          Записи не найдены.
                        </td>
                      </tr>
                    ) : (
                      filteredItems.map((role) => (
                        <tr key={roleIdOf(role)} className="border-t border-zinc-800 align-top">
                          <td className="px-5 py-4 text-sm text-zinc-100">{roleIdOf(role)}</td>
                          <td className="px-5 py-4 text-sm text-zinc-100">{roleCodeOf(role)}</td>
                          <td className="px-5 py-4 text-sm leading-5 text-zinc-100">{roleNameOf(role)}</td>
                          <td className="px-5 py-4 text-sm text-zinc-100">
                            {role.is_active ? "Да" : "Нет"}
                          </td>
                          <td className="px-5 py-4">
                            <div className="flex items-center gap-3">
                              <button
                                type="button"
                                onClick={() => openEdit(role)}
                                className="rounded-lg border border-zinc-800 bg-zinc-950/40 px-4 py-2 text-sm text-zinc-100 transition hover:bg-zinc-900/60"
                              >
                                Изменить
                              </button>

                              <button
                                type="button"
                                onClick={() => void handleDelete(role)}
                                className="rounded-lg border border-red-800 bg-transparent px-4 py-2 text-sm text-red-300 transition hover:bg-red-950/30"
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

      <RoleDrawer
        open={drawerOpen}
        mode={drawerMode}
        role={
          selectedRole
            ? {
                ...selectedRole,
                role_code: roleCodeOf(selectedRole),
                role_name: roleNameOf(selectedRole),
              }
            : null
        }
        saving={saving}
        error={drawerError}
        onClose={closeDrawer}
        onSubmit={handleSubmit}
      />
    </div>
  );
}