// FILE: corpsite-ui/app/directory/roles/_components/RolesPageClient.tsx
"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";

import { apiFetchJson } from "../../../../lib/api";
import RoleDrawer from "./RoleDrawer";
import type { RoleFormValues } from "./RoleForm";

type RoleItem = {
  role_id?: number | null;
  id?: number | null;
  role_code?: string | null;
  code?: string | null;
  role_name?: string | null;
  name?: string | null;
  description?: string | null;
  is_active?: boolean | null;
};

type RolesResponse =
  | RoleItem[]
  | {
      items?: RoleItem[];
      data?: RoleItem[];
      total?: number;
      filter_org_unit_id?: number | null;
      filter_org_unit_name?: string | null;
    };

const API_BASE = "/directory/roles";
const PAGE_SIZE = 50;

function roleIdOf(role: RoleItem): number {
  return Number(role.role_id ?? role.id ?? 0);
}

function roleCodeOf(role: RoleItem): string {
  return String(role.role_code ?? role.code ?? "").trim();
}

function roleNameOf(role: RoleItem): string {
  return String(role.role_name ?? role.name ?? "").trim();
}

function normalizeRoles(payload: RolesResponse): {
  items: RoleItem[];
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

function extractErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message) return error.message;
  return "Не удалось выполнить операцию.";
}

function parsePositiveInt(value: string | null): number | null {
  const n = Number(String(value ?? "").trim());
  if (!Number.isFinite(n) || n <= 0) return null;
  return Math.trunc(n);
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

export default function RolesPageClient() {
  const sp = useSearchParams();

  const orgUnitId = React.useMemo(() => readSelectedOrgUnitId(sp), [sp]);
  const orgUnitNameFromUrl = React.useMemo(() => {
    const v = String(sp.get("org_unit_name") ?? "").trim();
    return v || null;
  }, [sp]);

  const selectedRoleIdRef = React.useRef<number | null>(null);

  const [items, setItems] = React.useState<RoleItem[]>([]);
  const [total, setTotal] = React.useState(0);
  const [filterOrgUnitId, setFilterOrgUnitId] = React.useState<number | null>(null);
  const [filterOrgUnitName, setFilterOrgUnitName] = React.useState<string | null>(null);

  const [loading, setLoading] = React.useState(true);
  const [saving, setSaving] = React.useState(false);

  const [searchInput, setSearchInput] = React.useState(sp.get("q") ?? "");
  const [search, setSearch] = React.useState((sp.get("q") ?? "").trim());

  const [onlyActive, setOnlyActive] = React.useState(sp.get("is_active") === "true");
  const [page, setPage] = React.useState(0);

  const [pageError, setPageError] = React.useState<string | null>(null);
  const [drawerError, setDrawerError] = React.useState<string | null>(null);

  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [drawerMode, setDrawerMode] = React.useState<"create" | "edit">("create");
  const [selectedRole, setSelectedRole] = React.useState<RoleItem | null>(null);

  React.useEffect(() => {
    selectedRoleIdRef.current = selectedRole ? roleIdOf(selectedRole) : null;
  }, [selectedRole]);

  React.useEffect(() => {
    const timer = window.setTimeout(() => {
      const next = searchInput.trim();
      setPage(0);
      setSearch(next);
    }, 250);

    return () => window.clearTimeout(timer);
  }, [searchInput]);

  const loadRoles = React.useCallback(async () => {
    setLoading(true);
    setPageError(null);

    try {
      const params = new URLSearchParams();

      if (search) params.set("q", search);
      if (onlyActive) params.set("is_active", "true");
      if (orgUnitId != null) params.set("org_unit_id", String(orgUnitId));

      params.set("limit", String(PAGE_SIZE));
      params.set("offset", String(page * PAGE_SIZE));

      const url = `${API_BASE}?${params.toString()}`;
      const payload = await apiFetchJson<RolesResponse>(url);
      const normalized = normalizeRoles(payload);

      setItems(normalized.items);
      setTotal(normalized.total);
      setFilterOrgUnitId(normalized.filterOrgUnitId);
      setFilterOrgUnitName(normalized.filterOrgUnitName);

      const selectedId = selectedRoleIdRef.current;
      if (selectedId != null) {
        const stillVisible = normalized.items.some((role) => roleIdOf(role) === selectedId);
        if (!stillVisible) {
          setDrawerOpen(false);
          setSelectedRole(null);
          setDrawerError(null);
        }
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
  }, [search, onlyActive, orgUnitId, page]);

  React.useEffect(() => {
    void loadRoles();
  }, [loadRoles]);

  React.useEffect(() => {
    if (page > 0 && total > 0 && page * PAGE_SIZE >= total) {
      setPage(Math.max(0, Math.ceil(total / PAGE_SIZE) - 1));
    }
  }, [page, total]);

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

        setDrawerOpen(false);
        setSelectedRole(null);

        if (page !== 0) {
          setPage(0);
        } else {
          await loadRoles();
        }
      } else {
        const roleId = roleIdOf(selectedRole as RoleItem);

        await apiFetchJson(`${API_BASE}/${roleId}`, {
          method: "PUT",
          body: payload,
        });

        setDrawerOpen(false);
        setSelectedRole(null);
        await loadRoles();
      }
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
    <div className="bg-[#04070f] text-zinc-100">
      <div className="mx-auto w-full max-w-[1440px] px-4 py-3">
        <div className="overflow-hidden rounded-2xl border border-zinc-800 bg-[#050816]">
          <div className="border-b border-zinc-800 px-6 py-3">
            <h1 className="text-xl font-semibold leading-none text-zinc-100">
              Роли{filterCaption ? ` (${filterCaption})` : ""}
            </h1>
          </div>

          <div className="border-b border-zinc-800 px-6 py-2">
            <div className="flex flex-col gap-2 xl:flex-row xl:items-center">
              <div className="flex-1">
                <input
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  placeholder="Поиск по коду и названию"
                  className="h-8.5 w-full rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 py-1 text-sm text-zinc-100 outline-none transition placeholder:text-zinc-500 focus:border-zinc-600"
                />
              </div>

              <label className="flex h-8.5 min-w-[165px] items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 py-1 text-sm text-zinc-200">
                <input
                  type="checkbox"
                  checked={onlyActive}
                  onChange={(e) => {
                    setOnlyActive(e.target.checked);
                    setPage(0);
                  }}
                  className="h-3.5 w-3.5 rounded border-zinc-700 bg-zinc-900"
                />
                Только активные
              </label>

              <button
                type="button"
                onClick={() => void loadRoles()}
                className="h-8.5 rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 py-1 text-sm text-zinc-200 transition hover:bg-zinc-900/60"
              >
                Обновить
              </button>

              <button
                type="button"
                onClick={openCreate}
                className="h-8.5 rounded-lg bg-blue-600 px-3.5 py-1 text-sm font-medium text-white transition hover:bg-blue-500"
              >
                Создать роль
              </button>
            </div>
          </div>

          <div className="px-6 py-2">
            {!!pageError && (
              <div className="mb-2 rounded-xl border border-red-900/60 bg-red-950/40 px-4 py-2 text-sm text-red-200">
                {pageError}
              </div>
            )}

            <div className="mb-1.5 flex flex-col gap-1 text-[11px] text-zinc-400 md:flex-row md:items-center md:justify-between">
              <div>
                Всего: {total}
                {total > 0 ? <span className="ml-2">· показано: {pageFrom}–{pageTo}</span> : null}
              </div>

              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  onClick={() => setPage((prev) => Math.max(0, prev - 1))}
                  disabled={!hasPrev || loading}
                  className="rounded-lg border border-zinc-800 bg-zinc-950/40 px-2 py-0.5 text-[10px] text-zinc-200 transition hover:bg-zinc-900/60 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Назад
                </button>

                <div className="min-w-[52px] text-center text-[10px] text-zinc-400">
                  Стр. {page + 1}
                </div>

                <button
                  type="button"
                  onClick={() => setPage((prev) => prev + 1)}
                  disabled={!hasNext || loading}
                  className="rounded-lg border border-zinc-800 bg-zinc-950/40 px-2 py-0.5 text-[10px] text-zinc-200 transition hover:bg-zinc-900/60 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Вперёд
                </button>
              </div>
            </div>

            <div className="overflow-hidden rounded-2xl border border-zinc-800">
              <div className="overflow-x-auto">
                <table className="min-w-full border-collapse">
                  <thead>
                    <tr className="bg-white/[0.03] text-left">
                      <th className="px-4 py-1 text-[10px] font-medium uppercase tracking-[0.08em] text-zinc-400">
                        ID
                      </th>
                      <th className="px-4 py-1 text-[10px] font-medium uppercase tracking-[0.08em] text-zinc-400">
                        Код роли
                      </th>
                      <th className="px-4 py-1 text-[10px] font-medium uppercase tracking-[0.08em] text-zinc-400">
                        Название
                      </th>
                      <th className="px-4 py-1 text-[10px] font-medium uppercase tracking-[0.08em] text-zinc-400">
                        Активна
                      </th>
                      <th className="px-4 py-1 text-[10px] font-medium uppercase tracking-[0.08em] text-zinc-400">
                        Действия
                      </th>
                    </tr>
                  </thead>

                  <tbody>
                    {loading ? (
                      <tr>
                        <td colSpan={5} className="px-4 py-2 text-sm text-zinc-400">
                          Загрузка...
                        </td>
                      </tr>
                    ) : items.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="px-4 py-2 text-sm text-zinc-500">
                          Записи не найдены.
                        </td>
                      </tr>
                    ) : (
                      items.map((role) => (
                        <tr key={roleIdOf(role)} className="border-t border-zinc-800 align-top">
                          <td className="px-4 py-1 text-[13px] leading-4 text-zinc-100">
                            {roleIdOf(role)}
                          </td>

                          <td className="px-4 py-1 text-[13px] leading-4 text-zinc-100">
                            <div className="whitespace-nowrap">{roleCodeOf(role)}</div>
                          </td>

                          <td className="px-4 py-1 text-[13px] leading-4 text-zinc-100">
                            {roleNameOf(role)}
                          </td>

                          <td className="px-4 py-1 text-[13px] leading-4 text-zinc-100">
                            {role.is_active ? "Да" : "Нет"}
                          </td>

                          <td className="px-4 py-1">
                            <div className="flex flex-wrap items-center gap-1">
                              <button
                                type="button"
                                onClick={() => openEdit(role)}
                                className="rounded-lg border border-zinc-800 bg-zinc-950/40 px-1.5 py-0.5 text-[10px] leading-4 text-zinc-100 transition hover:bg-zinc-900/60"
                              >
                                Изменить
                              </button>

                              <button
                                type="button"
                                onClick={() => void handleDelete(role)}
                                className="rounded-lg border border-red-800 bg-transparent px-1.5 py-0.5 text-[10px] leading-4 text-red-300 transition hover:bg-red-950/30"
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