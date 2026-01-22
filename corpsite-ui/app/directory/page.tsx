// ROUTE: /directory  FILE: corpsite-ui/app/directory/page.tsx

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

  // Если URL меняется (навигация), синхронизируем init параметры
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
    <div style={{ padding: 16, display: "grid", gap: 14 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
        <div style={{ fontSize: 18, fontWeight: 800 }}>Сотрудники</div>
        <a href="/directory/org" style={{ fontSize: 13, opacity: 0.75 }}>
          перейти к оргструктуре
        </a>
        <a href="/directory/employees" style={{ fontSize: 13, opacity: 0.75 }}>
          открыть полный справочник
        </a>
      </div>

      <div style={{ border: "1px solid rgba(0,0,0,0.12)", borderRadius: 12, padding: 12 }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 160px 220px 160px", gap: 10 }}>
          <div>
            <div style={{ fontSize: 12, opacity: 0.7 }}>Поиск</div>
            <input
              value={q}
              onChange={(e) => {
                setOffset(0);
                setQ(e.target.value);
              }}
              placeholder="ФИО или табельный"
              style={{
                width: "100%",
                padding: "10px 10px",
                borderRadius: 10,
                border: "1px solid rgba(0,0,0,0.15)",
              }}
            />
          </div>

          <div>
            <div style={{ fontSize: 12, opacity: 0.7 }}>Статус</div>
            <select
              value={status}
              onChange={(e) => {
                setOffset(0);
                setStatus(e.target.value as Status);
              }}
              style={{
                width: "100%",
                padding: "10px 10px",
                borderRadius: 10,
                border: "1px solid rgba(0,0,0,0.15)",
                background: "white",
              }}
            >
              <option value="active">active</option>
              <option value="inactive">inactive</option>
              <option value="all">all</option>
            </select>
          </div>

          <div>
            <div style={{ fontSize: 12, opacity: 0.7 }}>org_unit_id</div>
            <input
              value={orgUnitId}
              onChange={(e) => {
                setOffset(0);
                setOrgUnitId(e.target.value.replace(/[^\d]/g, ""));
              }}
              placeholder="например 44"
              style={{
                width: "100%",
                padding: "10px 10px",
                borderRadius: 10,
                border: "1px solid rgba(0,0,0,0.15)",
              }}
            />
            <label style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 8, fontSize: 13 }}>
              <input
                type="checkbox"
                checked={includeChildren}
                onChange={(e) => {
                  setOffset(0);
                  setIncludeChildren(e.target.checked);
                }}
                disabled={!orgUnitId}
              />
              включая подотделы
            </label>
          </div>

          <div style={{ display: "flex", gap: 10, alignItems: "end" }}>
            <button
              type="button"
              onClick={() => {
                setQ("");
                setStatus("active");
                setOrgUnitId("");
                setIncludeChildren(false);
                setOffset(0);
              }}
              style={{
                padding: "10px 12px",
                borderRadius: 10,
                border: "1px solid rgba(0,0,0,0.15)",
                background: "white",
                cursor: "pointer",
                fontWeight: 600,
              }}
            >
              Сброс
            </button>
          </div>
        </div>
      </div>

      <div style={{ border: "1px solid rgba(0,0,0,0.12)", borderRadius: 12, padding: 12 }}>
        {loading && <div>Загрузка…</div>}
        {err && <div style={{ color: "crimson", whiteSpace: "pre-wrap" }}>Ошибка: {err}</div>}

        {!loading && !err && (
          <>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 10 }}>
              <div style={{ fontSize: 13, opacity: 0.75 }}>
                Показано {pageInfo.from}–{pageInfo.to} из {total}
              </div>

              <div style={{ display: "flex", gap: 8 }}>
                <button
                  type="button"
                  onClick={() => setOffset((v) => Math.max(0, v - limit))}
                  disabled={offset === 0}
                  style={{
                    padding: "8px 10px",
                    borderRadius: 10,
                    border: "1px solid rgba(0,0,0,0.15)",
                    background: "white",
                    cursor: "pointer",
                    opacity: offset === 0 ? 0.5 : 1,
                  }}
                >
                  Назад
                </button>
                <button
                  type="button"
                  onClick={() => setOffset((v) => (v + limit < total ? v + limit : v))}
                  disabled={offset + limit >= total}
                  style={{
                    padding: "8px 10px",
                    borderRadius: 10,
                    border: "1px solid rgba(0,0,0,0.15)",
                    background: "white",
                    cursor: "pointer",
                    opacity: offset + limit >= total ? 0.5 : 1,
                  }}
                >
                  Вперёд
                </button>
              </div>
            </div>

            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ textAlign: "left" }}>
                    {["Таб№", "ФИО", "Подразделение", "Должность", "Ставка", "Активен", ""].map((h) => (
                      <th
                        key={h}
                        style={{
                          padding: "10px 8px",
                          borderBottom: "1px solid rgba(0,0,0,0.12)",
                          fontSize: 12,
                          opacity: 0.75,
                        }}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {items.map((e: any) => {
                    const fio = pickName(e);
                    const unitName = e?.org_unit?.name || "";
                    const posName = e?.position?.name || "";
                    const rate = (e?.employment_rate ?? e?.rate) ?? null;
                    const active = e?.is_active;

                    return (
                      <tr key={e.id}>
                        <td style={{ padding: "10px 8px", borderBottom: "1px solid rgba(0,0,0,0.06)" }}>
                          <a
                            href={`/directory/employees/${encodeURIComponent(e.id)}`}
                            style={{ textDecoration: "none", fontWeight: 700 }}
                          >
                            {e.id}
                          </a>
                        </td>
                        <td style={{ padding: "10px 8px", borderBottom: "1px solid rgba(0,0,0,0.06)" }}>{fio}</td>
                        <td style={{ padding: "10px 8px", borderBottom: "1px solid rgba(0,0,0,0.06)" }}>{unitName}</td>
                        <td style={{ padding: "10px 8px", borderBottom: "1px solid rgba(0,0,0,0.06)" }}>{posName}</td>
                        <td style={{ padding: "10px 8px", borderBottom: "1px solid rgba(0,0,0,0.06)" }}>
                          {rate === null || rate === undefined ? "—" : String(rate)}
                        </td>
                        <td style={{ padding: "10px 8px", borderBottom: "1px solid rgba(0,0,0,0.06)" }}>
                          {active === true ? "да" : active === false ? "нет" : "—"}
                        </td>
                        <td style={{ padding: "10px 8px", borderBottom: "1px solid rgba(0,0,0,0.06)" }}>
                          <a href={`/directory/employees/${encodeURIComponent(e.id)}`} style={{ textDecoration: "none" }}>
                            открыть
                          </a>
                        </td>
                      </tr>
                    );
                  })}

                  {items.length === 0 && (
                    <tr>
                      <td colSpan={7} style={{ padding: 12, opacity: 0.7 }}>
                        Нет данных по текущим фильтрам.
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
  // Важно: useSearchParams() должен быть внутри Suspense boundary для prerender/SSG
  return (
    <Suspense fallback={<div style={{ padding: 16 }}>Загрузка…</div>}>
      <DirectoryHomeInner />
    </Suspense>
  );
}
