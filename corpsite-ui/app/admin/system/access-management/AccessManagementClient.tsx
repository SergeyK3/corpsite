"use client";

import { FormEvent, useState } from "react";

import { apiFetchJson } from "@/lib/api";

type UserItem = { user_id: number; login: string | null; is_active: boolean; role: string | null; lock_active: boolean; lock_reason: string | null; locked_until: string | null; employee_id: number | null; has_linked_employee: boolean };
type ResetResult = { temporary_password: string; must_change_password: boolean; token_version: number };

export default function AccessManagementClient() {
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<UserItem[]>([]);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [result, setResult] = useState<ResetResult | null>(null);
  const [copyHint, setCopyHint] = useState("");

  async function search(event: FormEvent) {
    event.preventDefault(); setError(""); setResult(null);
    try { const data = await apiFetchJson<{ items: UserItem[] }>(`/directory/access/users?q=${encodeURIComponent(query)}`); setItems(data.items); }
    catch { setError("Не удалось выполнить поиск учётных записей."); }
  }
  async function reset(userId: number) {
    if (!window.confirm("Выдать новый временный пароль? Предыдущий пароль перестанет работать.")) return;
    setBusyId(userId); setError(""); setCopyHint("");
    try { setResult(await apiFetchJson<ResetResult>(`/directory/access/users/${userId}/password-reset`, { method: "POST" })); }
    catch { setError("Не удалось выдать временный пароль."); }
    finally { setBusyId(null); }
  }
  async function copy() {
    if (!result) return;
    try { await navigator.clipboard.writeText(result.temporary_password); setCopyHint("Пароль скопирован."); }
    catch { setCopyHint("Не удалось скопировать пароль. Скопируйте его вручную."); }
  }
  return <main className="mx-auto max-w-5xl space-y-5 p-6" data-testid="access-management-page">
    <header><h1 className="text-2xl font-semibold">Управление доступом</h1><p className="mt-1 text-sm text-zinc-500">Поиск учётной записи и выдача временного пароля.</p></header>
    <form onSubmit={search} className="flex gap-2"><input aria-label="Поиск учётной записи" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Логин, имя или роль" className="w-full rounded border px-3 py-2" required /><button className="rounded bg-blue-600 px-4 py-2 text-white">Найти</button></form>
    {error ? <p className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-800">{error}</p> : null}
    {result ? <section className="rounded border border-amber-300 bg-amber-50 p-4" data-testid="access-reset-result"><h2 className="font-semibold">Временный пароль</h2><p className="mt-2 font-mono text-lg" data-testid="access-reset-password">{result.temporary_password}</p><button onClick={() => void copy()} className="mt-3 rounded border px-3 py-1">Копировать</button>{copyHint ? <p className="mt-2 text-sm">{copyHint}</p> : null}<p className="mt-3 text-sm">Передайте пароль сотруднику безопасным каналом. При входе потребуется сменить пароль.</p></section> : null}
    <section className="overflow-hidden rounded border"><table className="w-full text-sm"><thead className="bg-zinc-50 text-left"><tr><th className="p-3">Логин</th><th>Активность</th><th>Роль</th><th>Блокировка</th><th>Сотрудник</th><th /></tr></thead><tbody>{items.map((item) => <tr key={item.user_id} className="border-t"><td className="p-3">{item.login || "—"}</td><td>{item.is_active ? "Активен" : "Неактивен"}</td><td>{item.role || "—"}</td><td>{item.lock_active ? `${item.lock_reason || "Заблокирован"}${item.locked_until ? ` до ${item.locked_until}` : ""}` : "Нет"}</td><td>{item.has_linked_employee ? `Employee #${item.employee_id}` : "Не связан с сотрудником"}</td><td className="p-2"><button onClick={() => void reset(item.user_id)} disabled={busyId === item.user_id} className="rounded border px-2 py-1 disabled:opacity-50">{busyId === item.user_id ? "Выдача…" : "Выдать временный пароль"}</button></td></tr>)}</tbody></table></section>
  </main>;
}
