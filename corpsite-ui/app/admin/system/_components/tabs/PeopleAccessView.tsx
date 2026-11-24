"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchDepartmentGroups } from "@/lib/orgScope";
import { fetchAccessPeople, fetchAccessPerson, mapAdminSystemApiError, type AccessPersonAccount, type AccessPersonDetail, type AccessPersonRight, type AccessPeopleResponse, type AccessSource } from "../../_lib/adminSystemApi.client";

const stamp = (value: string | null | undefined) => value
  ? new Intl.DateTimeFormat("ru-RU", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value))
  : "дата неизвестна";

function scope(right: AccessPersonRight) {
  return right.scope_type === "GLOBAL" ? "Вся система"
    : right.scope_type === "SELF" ? "Свои данные"
    : right.scope_type === "ORG_UNIT" ? `Отделение: ${right.scope_unit_name || `#${right.scope_id ?? "?"}`}${right.include_subtree ? " и дочерние" : ""}`
    : `${right.scope_type}${right.scope_id == null ? "" : ` #${right.scope_id}`}`;
}

function sourceName(source: AccessSource) {
  if (source.source_type === "role") return `Роль «${source.role_name || source.role_code || source.target_id}»`;
  if (source.source_type === "personal") return "Персональная выдача";
  const targetNames: Record<string, string> = {
    EMPLOYEE: "сотрудника", PERSON: "физическое лицо", ASSIGNMENT: "назначение",
    POSITION: "должность", ORG_UNIT: "отделение",
  };
  return `Выдача на ${targetNames[source.target_type] || source.target_type} #${source.target_id}`;
}

function AccessSourceRow({ accountId, right, source }: { accountId: number; right: AccessPersonRight; source: AccessSource }) {
  const [open, setOpen] = useState(false);
  const detailId = `access-source-${accountId}-${source.grant_id}`;
  return <>
    <tr className={`border-t border-zinc-200 align-top dark:border-zinc-700 ${source.active ? "" : "bg-amber-50 dark:bg-amber-950/20"}`}>
      <td className="px-3 py-2">
        <button type="button" aria-expanded={open} aria-controls={detailId} onClick={() => setOpen((value) => !value)} className="flex w-full items-start gap-2 text-left font-medium text-zinc-900 hover:text-blue-700 dark:text-zinc-100 dark:hover:text-blue-300">
          <span aria-hidden="true" className="mt-0.5 text-zinc-500">{open ? "▾" : "▸"}</span>
          <span>{right.label}{!source.active && <span className="ml-2 rounded bg-amber-200 px-1.5 py-0.5 text-xs font-normal text-amber-950">Не действует</span>}</span>
        </button>
      </td>
      <td className="px-3 py-2">{sourceName(source)}</td>
      <td className="px-3 py-2">{scope(right)}</td>
      <td className="whitespace-nowrap px-3 py-2">{stamp(source.grant_created_at)}</td>
    </tr>
    {open && <tr id={detailId} className="border-t border-zinc-200 bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900/70">
      <td colSpan={4} className="px-5 py-2 text-sm">
        <div className="grid gap-x-6 gap-y-1 sm:grid-cols-2">
          <div>Код доступа: <span className="font-mono">{right.code}</span></div>
          {right.resource_key && <div>Код ресурса: <span className="font-mono">{right.resource_key}</span></div>}
          <div>Источник: {sourceName(source)} · выдача #{source.grant_id} · {source.status}</div>
          <div>Право выдано: {stamp(source.grant_created_at)}</div>
          {source.source_type === "role" && <div>Роль назначена сотруднику: {stamp(source.role_assigned_at)}</div>}
          <div>Действует с: {stamp(source.starts_at)}</div>
          <div>Действует до: {source.ends_at ? stamp(source.ends_at) : "без срока окончания"}</div>
          <div>Выдал: {source.grantor_label || (source.granted_by_user_id ? `USER:${source.granted_by_user_id}` : "неизвестно")}</div>
          <div>Причина: {source.reason || "не указана"}</div>
          {source.revoked_at && <div>Отозвано: {stamp(source.revoked_at)}; {source.revoker_label || (source.revoked_by_user_id ? `USER:${source.revoked_by_user_id}` : "автор неизвестен")}</div>}
          {source.audit.length > 0 && <div className="sm:col-span-2">События аудита: {source.audit.map((event) => `${event.event_type} ${stamp(event.happened_at)}${event.actor_label ? ` (${event.actor_label})` : ""}${event.reason ? ` — ${event.reason}` : ""}`).join("; ")}</div>}
        </div>
      </td>
    </tr>}
  </>;
}

function AccountRights({ account, showRevoked }: { account: AccessPersonAccount; showRevoked: boolean }) {
  const requestKey = `${account.user_id}:${showRevoked}`;
  const [result, setResult] = useState<{ key: string; detail?: AccessPersonDetail; error?: string } | null>(null);
  const detail = result?.key === requestKey ? result.detail ?? null : null;
  const error = result?.key === requestKey ? result.error ?? null : null;
  useEffect(() => {
    let live = true;
    void fetchAccessPerson(account.user_id, showRevoked)
      .then((data) => { if (live) setResult({ key: requestKey, detail: data }); })
      .catch((err) => { if (live) setResult({ key: requestKey, error: mapAdminSystemApiError(err, "Не удалось загрузить доступы") }); });
    return () => { live = false; };
  }, [account.user_id, showRevoked, requestKey]);
  const sections = useMemo(() => {
    const result = new Map<string, AccessPersonRight[]>();
    for (const right of detail?.items ?? []) result.set(right.section, [...(result.get(right.section) ?? []), right]);
    return result;
  }, [detail]);
  return <div className="mt-2 min-w-0 rounded-lg border border-zinc-200 bg-white p-3 dark:border-zinc-700 dark:bg-zinc-950">
    <div className="font-medium">{account.login || account.full_name || `USER:${account.user_id}`}
      {!account.is_active && <span className="ml-2 text-xs text-amber-700 dark:text-amber-300">Учётная запись неактивна</span>}
    </div>
    {error && <p role="alert" className="mt-2 text-sm text-red-700">{error}</p>}
    {!detail && !error && <p className="mt-2 text-sm text-zinc-500">Загрузка доступов…</p>}
    {detail && <>
      {detail.implicit_sources.map((item) => <p key={item} className="mt-2 rounded bg-amber-50 p-2 text-sm text-amber-900 dark:bg-amber-950/40 dark:text-amber-200">{item}</p>)}
      {sections.size === 0 && <p className="mt-2 text-sm text-zinc-500">Применимых выдач доступа нет.</p>}
      {sections.size > 0 && <div className="mt-2 max-w-full overflow-x-auto rounded border border-zinc-200 dark:border-zinc-700" role="region" aria-label={`Права учётной записи ${account.login || account.full_name || account.user_id}`} tabIndex={0}>
        <table className="w-full min-w-[840px] text-left text-sm text-zinc-700 dark:text-zinc-200">
          <colgroup><col className="w-[34%]" /><col className="w-[28%]" /><col className="w-[20%]" /><col className="w-[18%]" /></colgroup>
          <thead className="bg-zinc-100 text-zinc-700 dark:bg-zinc-900 dark:text-zinc-200"><tr>
            <th scope="col" className="px-3 py-2 font-semibold">Доступ</th>
            <th scope="col" className="px-3 py-2 font-semibold">Источник</th>
            <th scope="col" className="px-3 py-2 font-semibold">Область действия</th>
            <th scope="col" className="px-3 py-2 font-semibold">Дата выдачи</th>
          </tr></thead>
          {Array.from(sections.entries()).map(([section, rights]) => <tbody key={section}>
            <tr className="border-t border-zinc-200 bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900/50"><th scope="rowgroup" colSpan={4} className="px-3 py-1.5 font-semibold text-zinc-900 dark:text-zinc-100">{section}</th></tr>
            {rights.flatMap((right) => right.sources.map((source) => <AccessSourceRow key={source.grant_id} accountId={account.user_id} right={right} source={source} />))}
          </tbody>)}
        </table>
      </div>}
      <p className="mt-2 text-xs text-zinc-500">{detail.coverage_note}</p>
    </>}
  </div>;
}

function EmployeeRow({ row, showRevoked }: { row: AccessPeopleResponse["items"][number]; showRevoked: boolean }) {
  const [open, setOpen] = useState(false);
  return <details onToggle={(event) => setOpen(event.currentTarget.open)} className="rounded-lg border border-zinc-200 bg-white dark:border-zinc-700 dark:bg-zinc-950">
    <summary className="cursor-pointer p-3"><span className="font-medium">{row.full_name}</span><span className="ml-2 text-sm text-zinc-500">{row.users.map((user) => user.login || `USER:${user.user_id}`).join(", ") || "без учётной записи"}</span><div className="mt-1 text-sm text-zinc-600 dark:text-zinc-300">{row.has_current_assignment ? `${row.position_name || "Должность не указана"} · ${row.org_unit_name || "Отделение не указано"}` : row.org_unit_id != null ? `${row.position_name || "Должность не указана"} · ${row.org_unit_name || "Отделение не указано"} (по карточке сотрудника; нет текущего назначения)` : "Нет текущего назначения"}</div></summary>
    {open && <div className="border-t p-3 dark:border-zinc-700">{row.users.length ? row.users.map((account) => <AccountRights key={account.user_id} account={account} showRevoked={showRevoked} />) : <p className="text-sm text-zinc-500">Учётная запись не связана с сотрудником; доступы пользователя отсутствуют.</p>}</div>}
  </details>;
}

function UnlinkedAccounts({ accounts, showRevoked }: { accounts: AccessPersonAccount[]; showRevoked: boolean }) {
  const [open, setOpen] = useState(false);
  return <details onToggle={(event) => setOpen(event.currentTarget.open)} className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
    <summary className="cursor-pointer font-semibold">Учётные записи без сотрудника ({accounts.length})</summary>
    {open && <div className="mt-3 space-y-3">{accounts.map((account) => <div key={account.user_id} className="rounded border p-3 dark:border-zinc-700"><div>{account.full_name || account.login || `USER:${account.user_id}`}</div><AccountRights account={account} showRevoked={showRevoked} /></div>)}</div>}
  </details>;
}

export default function PeopleAccessView() {
  const [people, setPeople] = useState<AccessPeopleResponse | null>(null);
  const [groups, setGroups] = useState<Map<number, string>>(new Map());
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [groupId, setGroupId] = useState("");
  const [unitId, setUnitId] = useState("");
  const [positionId, setPositionId] = useState("");
  const [showRevoked, setShowRevoked] = useState(false);
  const [visibleCount, setVisibleCount] = useState(80);
  useEffect(() => {
    let live = true;
    void fetchAccessPeople().then((data) => { if (live) setPeople(data); })
      .catch((err) => { if (live) setError(mapAdminSystemApiError(err, "Не удалось загрузить сотрудников")); });
    void fetchDepartmentGroups().then((rows) => { if (live) setGroups(new Map(rows.map((row) => [row.group_id, row.group_name]))); }).catch(() => undefined);
    return () => { live = false; };
  }, []);
  const all = useMemo(() => people?.items ?? [], [people]);
  const groupOptions = useMemo(() => Array.from(new Set(all.map((row) => row.org_group_id).filter((id): id is number => id != null))).sort((a, b) => a - b), [all]);
  const units = useMemo(() => Array.from(new Map(all.filter((row) => !groupId || row.org_group_id === Number(groupId)).filter((row) => row.org_unit_id != null).map((row) => [row.org_unit_id, row.org_unit_name || `#${row.org_unit_id}`] as const)).entries()).sort((a, b) => a[1].localeCompare(b[1], "ru")), [all, groupId]);
  const positions = useMemo(() => Array.from(new Map(all.filter((row) => (!groupId || row.org_group_id === Number(groupId)) && (!unitId || row.org_unit_id === Number(unitId))).filter((row) => row.position_id != null).map((row) => [row.position_id, row.position_name || `#${row.position_id}`] as const)).entries()).sort((a, b) => a[1].localeCompare(b[1], "ru")), [all, groupId, unitId]);
  const filtered = useMemo(() => all.filter((row) => {
    if (groupId && row.org_group_id !== Number(groupId)) return false;
    if (unitId && row.org_unit_id !== Number(unitId)) return false;
    if (positionId && row.position_id !== Number(positionId)) return false;
    const search = query.trim().toLocaleLowerCase("ru");
    return !search || row.full_name.toLocaleLowerCase("ru").includes(search) || row.users.some((account) => (account.login || "").toLocaleLowerCase("ru").includes(search));
  }), [all, groupId, unitId, positionId, query]);
  const unlinked = (people?.unlinked_accounts ?? []).filter((account) => !query.trim() || `${account.login || ""} ${account.full_name || ""}`.toLocaleLowerCase("ru").includes(query.trim().toLocaleLowerCase("ru")));
  return <section className="space-y-4">
    <div className="rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-blue-950 dark:border-blue-900 dark:bg-blue-950/30 dark:text-blue-100">Просмотр выдач сотрудникам. Роль ADMIN и другие механизмы могут давать дополнительные допуски; перечень не является полным аудитом всех проверок приложения.</div>
    <div className="grid gap-3 rounded-lg border border-zinc-200 p-4 dark:border-zinc-700 sm:grid-cols-2 lg:grid-cols-5">
      <label className="text-sm lg:col-span-2">Поиск по ФИО или логину<input value={query} onChange={(event) => { setQuery(event.target.value); setVisibleCount(80); }} className="mt-1 w-full rounded border px-3 py-2 dark:border-zinc-600 dark:bg-zinc-900" placeholder="Начните вводить…" /></label>
      <label className="text-sm">Группа отделений<select value={groupId} onChange={(event) => { setGroupId(event.target.value); setUnitId(""); setPositionId(""); }} className="mt-1 w-full rounded border px-3 py-2 dark:border-zinc-600 dark:bg-zinc-900"><option value="">Все группы</option>{groupOptions.map((id) => <option key={id} value={id}>{groups.get(id) || `Группа ${id}`}</option>)}</select></label>
      <label className="text-sm">Отделение<select value={unitId} onChange={(event) => { setUnitId(event.target.value); setPositionId(""); }} className="mt-1 w-full rounded border px-3 py-2 dark:border-zinc-600 dark:bg-zinc-900"><option value="">Все отделения</option>{units.map(([id, name]) => <option key={id} value={id ?? ""}>{name}</option>)}</select></label>
      <label className="text-sm">Должность<select value={positionId} onChange={(event) => setPositionId(event.target.value)} className="mt-1 w-full rounded border px-3 py-2 dark:border-zinc-600 dark:bg-zinc-900"><option value="">Все должности</option>{positions.map(([id, name]) => <option key={id} value={id ?? ""}>{name}</option>)}</select></label>
    </div>
    <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={showRevoked} onChange={(event) => setShowRevoked(event.target.checked)} />Показать отозванные</label>
    {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
    {!people && !error && <p className="text-sm text-zinc-500">Загрузка сотрудников…</p>}
    {people && <>
      <h3 className="font-semibold">Сотрудники ({filtered.length})</h3>
      <div className="space-y-2">{filtered.slice(0, visibleCount).map((row) => <EmployeeRow key={row.employee_id} row={row} showRevoked={showRevoked} />)}</div>
      {filtered.length > visibleCount && <button type="button" onClick={() => setVisibleCount((count) => count + 80)} className="rounded border px-3 py-2 text-sm dark:border-zinc-700">Показать ещё</button>}
      {!groupId && !unitId && !positionId && <UnlinkedAccounts accounts={unlinked} showRevoked={showRevoked} />}
    </>}
  </section>;
}
