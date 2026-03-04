// FILE: corpsite-ui/app/directory/employees/_lib/api.client.ts

"use client";

import type { EmployeesResponse, EmployeeDetails } from "./types";
import { apiFetchJson } from "../../../../lib/api";

function buildQuery(params: Record<string, string | number | boolean | null | undefined>): Record<string, any> {
  const out: Record<string, any> = {};
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null) continue;
    const s = String(v).trim();
    if (!s) continue;
    out[k] = typeof v === "boolean" ? (v ? 1 : 0) : v;
  }
  return out;
}

function extractStatus(e: any): number | undefined {
  const s =
    (typeof e?.status === "number" && e.status) ||
    (typeof e?.details?.status === "number" && e.details.status) ||
    (typeof e?.details?.status_code === "number" && e.details.status_code);

  if (typeof s === "number" && Number.isFinite(s)) return s;

  const msg = typeof e?.message === "string" ? e.message : "";
  const m = msg.match(/\bHTTP\s+(\d{3})\b/i);
  if (m) {
    const n = Number(m[1]);
    if (Number.isFinite(n)) return n;
  }
  return undefined;
}

export function mapApiErrorToMessage(e: unknown): string {
  const anyErr: any = e as any;
  const status = extractStatus(anyErr);

  if (status === 401) return "Нет доступа (401).";
  if (status === 403) return "Недостаточно прав (403).";
  if (status === 404) return "Не найдено (404).";
  if (status && status >= 500) return "Ошибка сервера. Попробуйте позже.";

  const msg =
    (typeof anyErr?.message === "string" && anyErr.message.trim()) ||
    (typeof anyErr?.detail === "string" && anyErr.detail.trim()) ||
    "";

  return msg || "Ошибка запроса.";
}

/**
 * Список сотрудников
 * Backend: GET /directory/employees
 *
 * ВАЖНО:
 * apiFetchJson уже добавляет Authorization (Bearer) из sessionStorage,
 * поэтому здесь нельзя делать raw fetch без заголовков.
 */
export async function getEmployees(args: {
  status?: string;
  department_id?: number | string | null;
  position_id?: number | string | null;
  org_unit_id?: number | string | null;
  include_children?: boolean;
  q?: string | null;
  limit?: number | string;
  offset?: number | string;
}): Promise<EmployeesResponse> {
  const statusNorm = String(args.status ?? "all").trim().toLowerCase();

  const query = buildQuery({
    // "all" — НЕ отправляем (часто бекенд не понимает 'all' и возвращает 0)
    status: statusNorm === "all" ? undefined : statusNorm,

    department_id: args.department_id ?? undefined,
    position_id: args.position_id ?? undefined,
    org_unit_id: args.org_unit_id ?? undefined,

    // если бекенд поддерживает include_children для employees — передаём
    include_children: args.include_children ?? undefined,

    q: args.q ?? undefined,
    limit: args.limit ?? 50,
    offset: args.offset ?? 0,
  });

  return await apiFetchJson<EmployeesResponse>("/directory/employees", { query });
}

/**
 * Детали сотрудника
 */
export async function getEmployee(employeeId: string): Promise<EmployeeDetails> {
  const id = String(employeeId).trim();
  if (!id) throw new Error("Employee id is empty");
  return await apiFetchJson<EmployeeDetails>(`/directory/employees/${encodeURIComponent(id)}`, { method: "GET" });
}

/**
 * Завершение работы сотрудника
 * Backend: POST /directory/employees/{id}/terminate
 */
export async function terminateEmployee(employeeId: string, dateTo?: string): Promise<EmployeeDetails> {
  const id = String(employeeId).trim();
  if (!id) throw new Error("Employee id is empty");

  const dt = (dateTo ?? "").trim();
  const body = dt ? { date_to: dt } : undefined;

  return await apiFetchJson<EmployeeDetails>(`/directory/employees/${encodeURIComponent(id)}/terminate`, {
    method: "POST",
    body,
  });
}

/**
 * Должности
 */
export async function getPositions(args?: { limit?: number; offset?: number }): Promise<any> {
  const query = buildQuery({
    limit: args?.limit ?? 200,
    offset: args?.offset ?? 0,
  });
  return await apiFetchJson<any>("/directory/positions", { query });
}

/**
 * Отделы
 */
export async function getDepartments(args?: { limit?: number; offset?: number }): Promise<any> {
  const query = buildQuery({
    limit: args?.limit ?? 200,
    offset: args?.offset ?? 0,
  });
  return await apiFetchJson<any>("/directory/departments", { query });
}