"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";

import EmployeesTable from "./EmployeesTable";
import EmployeeDrawer from "./EmployeeDrawer";

import { getEmployees, getPositions, mapApiErrorToMessage } from "../_lib/api.client";
import type { EmployeeDTO, Position, Department, EmployeesResponse, EmployeeDetails } from "../_lib/types";

type Dept = Department;
type Pos = Position;

function buildQuery(params: Record<string, string | undefined>): string {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined) return;
    const s = String(v).trim();
    if (!s) return;
    q.set(k, s);
  });
  return q.toString();
}

function getDevUserId(): string | null {
  const v = process.env.NEXT_PUBLIC_DEV_X_USER_ID;
  return v && String(v).trim() ? String(v).trim() : null;
}

export default function EmployeesPageClient() {
  const router = useRouter();
  const sp = useSearchParams();

  // фильтры как строки (важно для select)
  const departmentId = sp.get("department_id") ?? "";
  const positionId = sp.get("position_id") ?? "";
  const status = sp.get("status") ?? "all";
  const qText = sp.get("q") ?? "";
  const limit = sp.get("limit") ?? "50";
  const offset = sp.get("offset") ?? "0";

  const [departments, setDepartments] = React.useState<Dept[]>([]);
  const [positions, setPositions] = React.useState<Pos[]>([]);

  const [data, setData] = React.useState<EmployeesResponse>({ items: [], total: 0 });
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [selectedEmployeeId, setSelectedEmployeeId] = React.useState<string | null>(null);

  const devUserId = getDevUserId();

  const apiBase =
    (process.env.NEXT_PUBLIC_API_BASE_URL || "").replace(/\/+$/, "") || "http://127.0.0.1:8000";

  function updateUrl(next: Partial<Record<string, string>>) {
    const nextParams = new URLSearchParams(sp.toString());

    Object.entries(next).forEach(([k, v]) => {
      const s = (v ?? "").trim();
      if (!s) nextParams.delete(k);
      else nextParams.set(k, s);
    });

    // при смене фильтров сбрасываем пагинацию
    nextParams.set("offset", "0");

    // limit/status держим стабильными
    if (!nextParams.get("limit")) nextParams.set("limit", "50");
    if (!nextParams.get("status")) nextParams.set("status", "all");

    router.replace(`/directory/employees?${nextParams.toString()}`);
  }

  function openDrawer(employeeId: string) {
    setSelectedEmployeeId(employeeId);
    setDrawerOpen(true);
  }

  function closeDrawer() {
    setDrawerOpen(false);
    setSelectedEmployeeId(null);
  }

  function onTerminate(details: EmployeeDetails) {
    // MVP: только хук под действие. Реальную “деактивацию/увольнение” подключим, когда будет endpoint.
    // Можно заменить на ваш modal/confirm.
    // eslint-disable-next-line no-alert
    alert(`TODO: завершить работу сотрудника: ${(details as any)?.fio ?? details.id}`);
  }

  // загрузка справочников (отделы/должности) один раз
  React.useEffect(() => {
    let cancelled = false;

    async function loadRefs() {
      try {
        const headers: Record<string, string> = { Accept: "application/json" };
        if (devUserId) headers["X-User-Id"] = devUserId;

        // departments пока нет в api.client.ts — оставляем прямой fetch
        const dRes = await fetch(`${apiBase}/directory/departments?limit=500&offset=0`, {
          method: "GET",
          headers,
          cache: "no-store",
        });

        let dItems: Dept[] = [];
        if (dRes.ok) {
          const dJson = await dRes.json().catch(() => null);
          dItems = Array.isArray(dJson?.items) ? (dJson.items as Dept[]) : [];
        }

        const pItems = await getPositions().catch(() => [] as Pos[]);

        if (cancelled) return;

        setDepartments(dItems);
        setPositions(pItems);
      } catch {
        if (cancelled) return;
        setDepartments([]);
        setPositions([]);
      }
    }

    loadRefs();
    return () => {
      cancelled = true;
    };
  }, [apiBase, devUserId]);

  // загрузка сотрудников — зависит от фильтров
  React.useEffect(() => {
    let cancelled = false;

    async function loadEmployees() {
      setLoading(true);
      setError(null);

      try {
        // Примечание: getEmployees сейчас поддерживает status/limit/offset.
        // department_id/position_id/q пока используем прямым fetch (так как API клиента не расширяли).
        const qs = buildQuery({
          status,
          department_id: departmentId || undefined,
          position_id: positionId || undefined,
          q: qText || undefined,
          limit,
          offset,
        });

        const headers: Record<string, string> = { Accept: "application/json" };
        if (devUserId) headers["X-User-Id"] = devUserId;

        const res = await fetch(`${apiBase}/directory/employees?${qs}`, {
          method: "GET",
          headers,
          cache: "no-store",
        });

        if (!res.ok) {
          const t = await res.text().catch(() => "");
          throw new Error(`HTTP ${res.status}: ${t || res.statusText}`);
        }

        const json = (await res.json()) as EmployeesResponse;

        if (cancelled) return;

        setData({
          items: Array.isArray(json?.items) ? (json.items as EmployeeDTO[]) : [],
          total: Number(json?.total ?? 0),
        });
      } catch (e) {
        if (cancelled) return;
        setError(mapApiErrorToMessage(e));
        setData({ items: [], total: 0 });
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadEmployees();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiBase, devUserId, departmentId, positionId, status, qText, limit, offset]);

  // EmployeesTable неизвестного контракта: подключаем selection максимально “мягко”
  const EmployeesTableAny = EmployeesTable as any;

  return (
    <div className="space-y-4">
      <div className="bg-white rounded border p-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div>
            <div className="text-xs text-gray-600 mb-1">Поиск</div>
            <input
              className="w-full border rounded px-3 py-2 text-sm"
              placeholder="ФИО или таб. №"
              value={qText}
              onChange={(e) => updateUrl({ q: e.target.value })}
            />
          </div>

          <div>
            <div className="text-xs text-gray-600 mb-1">Отдел</div>
            <select
              className="w-full border rounded px-3 py-2 text-sm"
              value={departmentId}
              onChange={(e) => updateUrl({ department_id: e.target.value })}
            >
              <option value="">Все</option>
              {departments.map((d) => (
                <option key={d.id} value={String(d.id)}>
                  {d.name ?? "—"}
                </option>
              ))}
            </select>
          </div>

          <div>
            <div className="text-xs text-gray-600 mb-1">Должность</div>
            <select
              className="w-full border rounded px-3 py-2 text-sm"
              value={positionId}
              onChange={(e) => updateUrl({ position_id: e.target.value })}
            >
              <option value="">Все</option>
              {positions.map((p) => (
                <option key={p.id} value={String(p.id)}>
                  {p.name ?? "—"}
                </option>
              ))}
            </select>
          </div>

          <div>
            <div className="text-xs text-gray-600 mb-1">Статус</div>
            <select
              className="w-full border rounded px-3 py-2 text-sm"
              value={status}
              onChange={(e) => updateUrl({ status: e.target.value })}
            >
              <option value="all">Все</option>
              <option value="active">Работает</option>
              <option value="inactive">Не работает</option>
            </select>
          </div>
        </div>
      </div>

      {error ? (
        <div className="bg-white rounded border p-4 text-red-600 text-sm">{error}</div>
      ) : null}

      <EmployeesTableAny
        items={data.items}
        total={data.total}
        loading={loading}
        onRowClick={(row: EmployeeDTO) => openDrawer(row.id)}
        onSelectEmployeeId={(id: string) => openDrawer(id)}
      />

      <EmployeeDrawer
        employeeId={selectedEmployeeId}
        open={drawerOpen}
        onClose={closeDrawer}
        onTerminate={onTerminate}
      />
    </div>
  );
}
