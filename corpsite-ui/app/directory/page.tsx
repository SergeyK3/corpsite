// ROUTE: /directory
// FILE: corpsite-ui/app/directory/page.tsx

"use client";

import React, { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";

import { getEmployees } from "../directory/employees/_lib/api.client";
import type { EmployeeDTO as EmployeeListItem } from "../directory/employees/_lib/types";

type Status = "active" | "inactive" | "all";

function pickName(e: any): string {
  return e?.full_name || e?.fio || "";
}

function DirectoryHomeInner() {
  const sp = useSearchParams();

  const initOrgUnitId = sp.get("org_unit_id") || "";
  const initIncludeChildren = (sp.get("include_children") || "false").toLowerCase() === "true";

  const [q, setQ] = useState<string>("");
  const [status, setStatus] = useState<Status>("active");
  const [orgUnitId, setOrgUnitId] = useState<string>(initOrgUnitId);
  const [includeChildren, setIncludeChildren] = useState<boolean>(initIncludeChildren);

  const [items, setItems] = useState<EmployeeListItem[]>([]);
  const [total, setTotal] = useState<number>(0);

  const [limit] = useState<number>(50);
  const [offset, setOffset] = useState<number>(0);

  const [loading, setLoading] = useState<boolean>(true);
  const [err, setErr] = useState<string>("");

  useEffect(() => {
    setOrgUnitId(initOrgUnitId);
    setIncludeChildren(initIncludeChildren);
    setOffset(0);
  }, [initOrgUnitId, initIncludeChildren]);

  const query = useMemo(() => {
    const out: any = {
      status,
      q: q || undefined,
      limit,
      offset,
    };
    if (orgUnitId) out.org_unit_id = Number(orgUnitId);
    if (orgUnitId) out.include_children = includeChildren;
    return out;
  }, [status, q, limit, offset, orgUnitId, includeChildren]);

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true);
      setErr("");
      try {
        const res = await getEmployees(query);
        if (!alive) return;
        setItems(res.items || []);
        setTotal(Number(res.total || 0));
      } catch (e: any) {
        if (!alive) return;
        setErr(e?.message || String(e));
      } finally {
        if (!alive) return;
        setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [query]);

  const pageInfo = useMemo(() => {
    const from = total === 0 ? 0 : offset + 1;
    const to = Math.min(offset + limit, total);
    return { from, to };
  }, [offset, limit, total]);

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      {/* TITLE */}
      <div className="mb-6">
        <div className="text-2xl font-semibold text-zinc-100">Оргструктура</div>
        <div className="mt-1 text-sm text-zinc-400">
          Просмотр подразделений и сотрудников (только для чтения)
        </div>
      </div>

      {/* LINKS */}
      <div className="mb-6 flex flex-wrap gap-4 text-sm">
        <a href="/directory/org" className="text-blue-400 hover:underline">
          Открыть дерево подразделений
        </a>
        <a href="/directory/employees" className="text-blue-400 hover:underline">
          Полный справочник сотрудников
        </a>
      </div>

      {/* SEARCH BLOCK */}
      <div className="mb-6 rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div>
            <div className="mb-1 text-xs text-zinc-400">Поиск</div>
            <input
              value={q}
              onChange={(e) => {
                setOffset(0);
                setQ(e.target.value);
              }}
              placeholder="ФИО или табельный номер"
              className="w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none"
            />
          </div>

          <div>
            <div className="mb-1 text-xs text-zinc-400">Статус</div>
            <select
              value={status}
              onChange={(e) => {
                setOffset(0);
                setStatus(e.target.value as Status);
              }}
              className="w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none"
            >
              <option value="active">Активные</option>
              <option value="inactive">Неактивные</option>
              <option value="all">Все</option>
            </select>
          </div>

          <div className="flex items-end">
            <button
              onClick={() => {
                setQ("");
                setStatus("active");
                setOrgUnitId("");
                setIncludeChildren(false);
                setOffset(0);
              }}
              className="w-full rounded-md border border-zinc-800 bg-zinc-950/40 px-4 py-2 text-sm text-zinc-200 hover:bg-zinc-900/60"
            >
              Сбросить фильтры
            </button>
          </div>
        </div>
      </div>

      {/* TABLE */}
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
        {loading && <div className="text-sm text-zinc-400">Загрузка…</div>}
        {err && <div className="text-sm text-red-400">Ошибка: {err}</div>}

        {!loading && !err && (
          <>
            <div className="mb-4 flex justify-between text-xs text-zinc-400">
              <div>
                Показано {pageInfo.from}–{pageInfo.to} из {total}
              </div>

              <div className="flex gap-2">
                <button
                  onClick={() => setOffset((v) => Math.max(0, v - limit))}
                  disabled={offset === 0}
                  className="rounded-md border border-zinc-800 bg-zinc-950/40 px-3 py-1 text-zinc-200 disabled:opacity-50"
                >
                  Назад
                </button>
                <button
                  onClick={() => setOffset((v) => (v + limit < total ? v + limit : v))}
                  disabled={offset + limit >= total}
                  className="rounded-md border border-zinc-800 bg-zinc-950/40 px-3 py-1 text-zinc-200 disabled:opacity-50"
                >
                  Вперёд
                </button>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr className="text-left text-xs text-zinc-400">
                    <th className="border-b border-zinc-800 px-2 py-2">Таб№</th>
                    <th className="border-b border-zinc-800 px-2 py-2">ФИО</th>
                    <th className="border-b border-zinc-800 px-2 py-2">Подразделение</th>
                    <th className="border-b border-zinc-800 px-2 py-2">Должность</th>
                    <th className="border-b border-zinc-800 px-2 py-2">Активен</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((e: any) => {
                    const fio = pickName(e);
                    const unitName = e?.org_unit?.name || "";
                    const posName = e?.position?.name || "";
                    const active = e?.is_active;

                    return (
                      <tr key={e.id}>
                        <td className="border-b border-zinc-800 px-2 py-2 font-medium text-zinc-200">
                          {e.id}
                        </td>
                        <td className="border-b border-zinc-800 px-2 py-2 text-zinc-100">{fio}</td>
                        <td className="border-b border-zinc-800 px-2 py-2 text-zinc-300">{unitName}</td>
                        <td className="border-b border-zinc-800 px-2 py-2 text-zinc-300">{posName}</td>
                        <td className="border-b border-zinc-800 px-2 py-2 text-zinc-300">
                          {active === true ? "да" : active === false ? "нет" : "—"}
                        </td>
                      </tr>
                    );
                  })}

                  {items.length === 0 && (
                    <tr>
                      <td colSpan={5} className="px-3 py-4 text-center text-zinc-500">
                        Нет данных.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function DirectoryHomePage() {
  return (
    <Suspense fallback={<div style={{ padding: 16 }}>Загрузка…</div>}>
      <DirectoryHomeInner />
    </Suspense>
  );
}
