// corpsite-ui/app/directory/employees/_lib/api.client.ts

import type {
  EmployeesResponse,
  EmployeeDetails,
} from "./types";

function getApiBase(): string {
  const v = (process.env.NEXT_PUBLIC_API_BASE_URL || "").trim().replace(/\/+$/, "");
  return v || "http://127.0.0.1:8000";
}

function getDevUserId(): string | null {
  const v = (process.env.NEXT_PUBLIC_DEV_X_USER_ID || "").trim();
  return v ? v : null;
}

function buildQuery(params: Record<string, string | number | null | undefined>): string {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === null) return;
    const s = String(v).trim();
    if (!s) return;
    q.set(k, s);
  });
  return q.toString();
}

/**
 * Единая мапа ошибок fetch/HTTP → человеко-читаемый текст для UI.
 * Важно: экспортируется и используется в компонентах.
 */
export function mapApiErrorToMessage(e: unknown): string {
  const msg = e instanceof Error ? e.message : String(e ?? "Unknown error");

  // Пытаемся вытащить HTTP статус из типового текста ошибок
  const m = msg.match(/\bHTTP\s+(\d{3})\b/i);
  const status = m ? Number(m[1]) : undefined;

  if (status === 401) return "Нет доступа (401).";
  if (status === 403) return "Недостаточно прав (403).";
  if (status === 404) return "Не найдено (404).";
  if (status && status >= 500) return "Ошибка сервера. Попробуйте позже.";
  return msg || "Ошибка запроса.";
}

async function apiGetJson<T>(path: string, qs?: string): Promise<T> {
  const apiBase = getApiBase();
  const devUserId = getDevUserId();

  const headers: Record<string, string> = { Accept: "application/json" };
  if (devUserId) headers["X-User-Id"] = devUserId;

  const url = qs ? `${apiBase}${path}?${qs}` : `${apiBase}${path}`;

  const res = await fetch(url, {
    method: "GET",
    headers,
    cache: "no-store",
  });

  if (!res.ok) {
    const t = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status}: ${t || res.statusText}`);
  }

  return (await res.json()) as T;
}

/**
 * Список сотрудников
 */
export async function getEmployees(args: {
  status?: string;
  department_id?: number | string | null;
  position_id?: number | string | null;
  org_unit_id?: number | string | null;
  q?: string | null;
  limit?: number | string;
  offset?: number | string;
}): Promise<EmployeesResponse> {
  const qs = buildQuery({
    status: args.status ?? "all",
    department_id: args.department_id ?? undefined,
    position_id: args.position_id ?? undefined,
    org_unit_id: args.org_unit_id ?? undefined,
    q: args.q ?? undefined,
    limit: args.limit ?? 50,
    offset: args.offset ?? 0,
  });

  return apiGetJson<EmployeesResponse>("/directory/employees", qs);
}

/**
 * Детали сотрудника
 */
export async function getEmployee(employeeId: string): Promise<EmployeeDetails> {
  const id = String(employeeId).trim();
  if (!id) throw new Error("Employee id is empty");
  return apiGetJson<EmployeeDetails>(`/directory/employees/${encodeURIComponent(id)}`);
}

/**
 * Должности (если endpoint у вас реально есть)
 * Если backend возвращает { items, total } — компонент отработает.
 */
export async function getPositions(args?: { limit?: number; offset?: number }): Promise<any> {
  const qs = buildQuery({
    limit: args?.limit ?? 200,
    offset: args?.offset ?? 0,
  });
  return apiGetJson<any>("/directory/positions", qs);
}

/**
 * Отделы (опционально; если используете)
 */
export async function getDepartments(args?: { limit?: number; offset?: number }): Promise<any> {
  const qs = buildQuery({
    limit: args?.limit ?? 200,
    offset: args?.offset ?? 0,
  });
  return apiGetJson<any>("/directory/departments", qs);
}
