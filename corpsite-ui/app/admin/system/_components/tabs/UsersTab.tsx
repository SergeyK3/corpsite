// FILE: corpsite-ui/app/admin/system/_components/tabs/UsersTab.tsx
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useCurrentUser } from "@/lib/currentUser";

import {
  fetchAdminUsers,
  createDocumentationUser,
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
  const me = useCurrentUser();
  const canCreate = Number(me?.role_id) === 2 && !me?.is_documentation_viewer;
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [fullName, setFullName] = useState("");
  const [login, setLogin] = useState("");
  const [temporaryPassword, setTemporaryPassword] = useState("");
  const [profileCode, setProfileCode] = useState<"DOCUMENTATION_VIEWER" | "SYSADMIN_ASSISTANT">("DOCUMENTATION_VIEWER");
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

  async function submitCreate(event: React.FormEvent) {
    event.preventDefault();
    if (creating || !canCreate) return;
    setCreating(true); setError(null); setSuccess(null);
    try {
      const created = await createDocumentationUser({ full_name: fullName.trim(), login: login.trim(), temporary_password: temporaryPassword, profile_code: profileCode });
      setTemporaryPassword(""); setLogin(""); setFullName(""); setCreateOpen(false);
      setSuccess(`Создан аккаунт ${created.login}. При первом входе потребуется сменить пароль.`);
      await load();
    } catch (err) {
      setError(mapAdminSystemApiError(err, "Не удалось создать аккаунт"));
    } finally { setCreating(false); }
  }

  return (
    <div className="space-y-4">
      <ErrorBanner message={error} />
      <SuccessBanner message={success} />

      {canCreate ? <button type="button" onClick={() => { setCreateOpen(true); setError(null); }}
        className="rounded-lg bg-blue-600 px-3 py-2 text-sm text-white">Создать аккаунт для руководства</button> : null}
      {canCreate && createOpen ? <form onSubmit={submitCreate} aria-label="Создание самостоятельного аккаунта" className="space-y-3 rounded-lg border p-4">
        <h2 className="font-semibold">Самостоятельный аккаунт</h2>
        <label className="block">Профиль<select value={profileCode} onChange={e => setProfileCode(e.target.value as typeof profileCode)} className="ml-2 rounded border p-2 dark:bg-zinc-900">
          <option value="DOCUMENTATION_VIEWER">DOCUMENTATION_VIEWER — просмотр</option>
          <option value="SYSADMIN_ASSISTANT">SYSADMIN_ASSISTANT — Помощник системного администратора</option>
        </select></label>
        <p className="text-sm text-zinc-500">{profileCode === "DOCUMENTATION_VIEWER" ? "Просмотр без сохранения." : "Помощник может создавать и редактировать кадровые приказы, регистрировать и применять их к реальным сотрудникам. Управление системой, справочниками и шаблонами закрыто."} Сотрудник не создаётся. При первом входе обязательна смена пароля.</p>
        <label className="block">Имя<input required maxLength={200} value={fullName} onChange={e => setFullName(e.target.value)} className="ml-2 rounded border p-2 dark:bg-zinc-900" /></label>
        <label className="block">Логин<input required maxLength={200} autoComplete="off" value={login} onChange={e => setLogin(e.target.value)} className="ml-2 rounded border p-2 dark:bg-zinc-900" /></label>
        <label className="block">Временный пароль<input required type="password" minLength={8} maxLength={200} autoComplete="new-password" value={temporaryPassword} onChange={e => setTemporaryPassword(e.target.value)} className="ml-2 rounded border p-2 dark:bg-zinc-900" /></label>
        <div className="flex gap-3"><button type="submit" disabled={creating} className="rounded bg-blue-600 px-3 py-2 text-white">{creating ? "Создание…" : "Создать аккаунт"}</button>
          <button type="button" disabled={creating} onClick={() => { setCreateOpen(false); setTemporaryPassword(""); }}>Отмена</button></div>
      </form> : null}

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
