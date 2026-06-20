// FILE: corpsite-ui/app/admin/system/_components/tabs/UsersTab.tsx
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  fetchAdminUsers,
  forcePasswordChangeAdminUser,
  lockAdminUser,
  mapAdminSystemApiError,
  unlockAdminUser,
  type AdminUser,
} from "../../_lib/adminSystemApi.client";
import { formatDateTime } from "../../_lib/adminSystemLabels";
import ErrorBanner, { SuccessBanner } from "../shared/ErrorBanner";

function userStatusLabel(u: AdminUser): string {
  const parts: string[] = [];
  parts.push(u.is_active === false ? "inactive" : "active");
  if (u.locked_at) parts.push("locked");
  if (u.must_change_password) parts.push("must_change_password");
  return parts.join(" · ");
}

export default function UsersTab() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const rows = await fetchAdminUsers({ limit: 500 });
      setUsers(rows);
    } catch (err) {
      setError(mapAdminSystemApiError(err, "Не удалось загрузить пользователей"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return users;
    return users.filter((u) => {
      const hay = [u.login, u.full_name, String(u.user_id), u.role_name]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });
  }, [users, search]);

  async function runAction(
    userId: number,
    action: "lock" | "unlock" | "force",
  ): Promise<void> {
    setBusyId(userId);
    setError(null);
    setSuccess(null);
    try {
      if (action === "lock") await lockAdminUser(userId);
      else if (action === "unlock") await unlockAdminUser(userId);
      else await forcePasswordChangeAdminUser(userId);
      setSuccess(`Действие выполнено для user #${userId}`);
      await load();
    } catch (err) {
      const msg = mapAdminSystemApiError(err, "Не удалось выполнить действие");
      if (msg.includes("501") || msg.toLowerCase().includes("not implemented")) {
        setError("Будет реализовано позже.");
      } else {
        setError(msg);
      }
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-4">
      <ErrorBanner message={error} />
      <SuccessBanner message={success} />

      <div className="flex flex-wrap items-center gap-3">
        <input
          type="search"
          placeholder="Поиск по login, имени, ID…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="min-w-[220px] rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-600 dark:bg-zinc-900"
        />
        <button
          type="button"
          onClick={() => void load()}
          className="rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-600"
        >
          Обновить
        </button>
      </div>

      {loading ? (
        <p className="text-sm text-zinc-500">Загрузка…</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-700">
          <table className="min-w-full text-sm">
            <thead className="bg-zinc-50 text-left dark:bg-zinc-900">
              <tr>
                <th className="px-3 py-2">ID</th>
                <th className="px-3 py-2">Login</th>
                <th className="px-3 py-2">Имя</th>
                <th className="px-3 py-2">Роль</th>
                <th className="px-3 py-2">Статус</th>
                <th className="px-3 py-2">Действия</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((u) => (
                <tr key={u.user_id} className="border-t border-zinc-100 dark:border-zinc-800">
                  <td className="px-3 py-2">{u.user_id}</td>
                  <td className="px-3 py-2">{u.login ?? "—"}</td>
                  <td className="px-3 py-2">{u.full_name ?? "—"}</td>
                  <td className="px-3 py-2">{u.role_name ?? u.role_id ?? "—"}</td>
                  <td className="px-3 py-2">
                    <span className="text-xs">{userStatusLabel(u)}</span>
                    {u.locked_at ? (
                      <div className="text-xs text-zinc-500">
                        locked {formatDateTime(u.locked_at)}
                        {u.locked_reason ? ` (${u.locked_reason})` : ""}
                      </div>
                    ) : null}
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap gap-1">
                      <button
                        type="button"
                        disabled={busyId === u.user_id}
                        onClick={() => void runAction(u.user_id, "lock")}
                        className="rounded border px-2 py-0.5 text-xs dark:border-zinc-600"
                      >
                        Заблокировать
                      </button>
                      <button
                        type="button"
                        disabled={busyId === u.user_id}
                        onClick={() => void runAction(u.user_id, "unlock")}
                        className="rounded border px-2 py-0.5 text-xs dark:border-zinc-600"
                      >
                        Разблокировать
                      </button>
                      <button
                        type="button"
                        disabled={busyId === u.user_id}
                        onClick={() => void runAction(u.user_id, "force")}
                        className="rounded border px-2 py-0.5 text-xs dark:border-zinc-600"
                      >
                        Требовать смену пароля
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
