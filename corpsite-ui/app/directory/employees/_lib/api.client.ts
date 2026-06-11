// FILE: corpsite-ui/app/directory/employees/_lib/api.client.ts

import type {
  EmployeesResponse,
  EmployeeDetails,
  EmployeeCreatePayload,
  EmployeeUpdatePayload,
  UserDTO,
  UserCreatePayload,
} from "./types";
import { getSessionAccessToken } from "@/lib/auth";
import { formatThrownError } from "@/lib/i18n";

function getApiBase(): string {
  const v = (process.env.NEXT_PUBLIC_API_BASE_URL || "").trim().replace(/\/+$/, "");
  return v || "http://127.0.0.1:8000";
}

function getDevUserId(): string | null {
  const appEnv = (process.env.NEXT_PUBLIC_APP_ENV || "dev").trim().toLowerCase();
  if (appEnv === "prod" || appEnv === "production") return null;
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
export function mapApiErrorToMessage(e: unknown, fallback = "Ошибка запроса."): string {
  return formatThrownError(e, { fallback });
}

function maybeAddAuthHeader(headers: Record<string, string>) {
  const token = String(getSessionAccessToken?.() ?? "").trim();
  if (token) headers.Authorization = `Bearer ${token}`;
}

async function apiGetJson<T>(path: string, qs?: string): Promise<T> {
  const apiBase = getApiBase();
  const devUserId = getDevUserId();

  const headers: Record<string, string> = { Accept: "application/json" };
  if (devUserId) headers["X-User-Id"] = devUserId;
  maybeAddAuthHeader(headers);

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

async function apiPostJson<T>(path: string, body?: unknown): Promise<T> {
  const apiBase = getApiBase();
  const devUserId = getDevUserId();

  const headers: Record<string, string> = {
    Accept: "application/json",
    "Content-Type": "application/json",
  };
  if (devUserId) headers["X-User-Id"] = devUserId;
  maybeAddAuthHeader(headers);

  const res = await fetch(`${apiBase}${path}`, {
    method: "POST",
    headers,
    body: body ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });

  if (!res.ok) {
    const t = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status}: ${t || res.statusText}`);
  }

  return (await res.json()) as T;
}

async function apiPatchJson<T>(path: string, body?: unknown): Promise<T> {
  const apiBase = getApiBase();
  const devUserId = getDevUserId();

  const headers: Record<string, string> = {
    Accept: "application/json",
    "Content-Type": "application/json",
  };
  if (devUserId) headers["X-User-Id"] = devUserId;
  maybeAddAuthHeader(headers);

  const res = await fetch(`${apiBase}${path}`, {
    method: "PATCH",
    headers,
    body: body ? JSON.stringify(body) : undefined,
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
  org_group_id?: number | string | null;
  org_unit_id?: number | string | null;
  include_children?: boolean;
  q?: string | null;
  limit?: number | string;
  offset?: number | string;
}): Promise<EmployeesResponse> {
  const qs = buildQuery({
    status: args.status ?? "all",
    department_id: args.department_id ?? undefined,
    position_id: args.position_id ?? undefined,
    org_group_id: args.org_group_id ?? undefined,
    org_unit_id: args.org_unit_id ?? undefined,
    include_children: args.include_children ? "true" : undefined,
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
 * Завершение работы сотрудника
 * Backend: POST /directory/employees/{id}/terminate
 *
 * Совместимость с UI:
 * - terminateEmployee(id)
 * - terminateEmployee(id, dateTo)  // dateTo: "YYYY-MM-DD"
 */
export async function terminateEmployee(employeeId: string, dateTo?: string): Promise<EmployeeDetails> {
  const id = String(employeeId).trim();
  if (!id) throw new Error("Employee id is empty");

  const dt = (dateTo ?? "").trim();
  const body = dt ? { date_to: dt } : undefined;

  return apiPostJson<EmployeeDetails>(`/directory/employees/${encodeURIComponent(id)}/terminate`, body);
}

/**
 * Создание сотрудника
 * Backend: POST /directory/employees
 */
export async function createEmployee(body: EmployeeCreatePayload): Promise<EmployeeDetails> {
  const full_name = String(body.full_name ?? "").trim();
  if (!full_name) throw new Error("full_name is required");

  const org_unit_id = Number(body.org_unit_id);
  const position_id = Number(body.position_id);
  if (!Number.isFinite(org_unit_id) || org_unit_id < 1) throw new Error("org_unit_id is required");
  if (!Number.isFinite(position_id) || position_id < 1) throw new Error("position_id is required");

  const payload: Record<string, unknown> = {
    full_name,
    org_unit_id,
    position_id,
  };

  const dateFrom = String(body.date_from ?? "").trim();
  if (dateFrom) payload.date_from = dateFrom;

  if (body.employment_rate != null && Number.isFinite(Number(body.employment_rate))) {
    payload.employment_rate = Number(body.employment_rate);
  }

  return apiPostJson<EmployeeDetails>("/directory/employees", payload);
}

/**
 * Редактирование сотрудника
 * Backend: PATCH /directory/employees/{id}
 */
export async function updateEmployee(
  employeeId: string,
  body: EmployeeUpdatePayload
): Promise<EmployeeDetails> {
  const id = String(employeeId).trim();
  if (!id) throw new Error("Employee id is empty");

  const payload: Record<string, unknown> = {};

  if (body.full_name != null) {
    const full_name = String(body.full_name).trim();
    if (!full_name) throw new Error("full_name is required");
    payload.full_name = full_name;
  }

  if (body.date_from != null) {
    const dateFrom = String(body.date_from).trim();
    if (dateFrom) payload.date_from = dateFrom;
  }

  if (body.employment_rate != null && Number.isFinite(Number(body.employment_rate))) {
    payload.employment_rate = Number(body.employment_rate);
  }

  if (body.position_id != null) {
    const position_id = Number(body.position_id);
    if (!Number.isFinite(position_id) || position_id < 1) throw new Error("position_id is required");
    payload.position_id = position_id;
  }

  if (Object.keys(payload).length === 0) {
    throw new Error("At least one field is required");
  }

  return apiPatchJson<EmployeeDetails>(`/directory/employees/${encodeURIComponent(id)}`, payload);
}

/**
 * Пользователь по employee_id
 * Backend: GET /directory/users?employee_id=
 */
export async function getUserByEmployeeId(employeeId: number | string): Promise<UserDTO> {
  const id = Number(employeeId);
  if (!Number.isFinite(id) || id < 1) throw new Error("employee_id is required");
  const qs = buildQuery({ employee_id: id });
  return apiGetJson<UserDTO>("/directory/users", qs);
}

/**
 * Создание пользователя для сотрудника
 * Backend: POST /directory/users
 */
export async function createUser(body: UserCreatePayload): Promise<UserDTO> {
  const employee_id = Number(body.employee_id);
  const role_id = Number(body.role_id);
  const login = String(body.login ?? "").trim();
  const password = String(body.password ?? "");

  if (!Number.isFinite(employee_id) || employee_id < 1) throw new Error("employee_id is required");
  if (!Number.isFinite(role_id) || role_id < 1) throw new Error("role_id is required");
  if (!login) throw new Error("login is required");
  if (password.length < 8) throw new Error("password must be at least 8 characters");

  const payload: Record<string, unknown> = {
    employee_id,
    role_id,
    login,
    password,
    is_active: body.is_active !== false,
  };

  if (body.unit_id != null && Number.isFinite(Number(body.unit_id))) {
    payload.unit_id = Number(body.unit_id);
  }

  return apiPostJson<UserDTO>("/directory/users", payload);
}

/**
 * Роли (для select при создании пользователя)
 */
export async function getRoles(args?: { limit?: number; offset?: number }): Promise<any> {
  const qs = buildQuery({
    limit: args?.limit ?? 200,
    offset: args?.offset ?? 0,
  });
  return apiGetJson<any>("/directory/roles", qs);
}

/**
 * Должности
 */
export async function getPositions(args?: {
  limit?: number;
  offset?: number;
  org_unit_id?: number;
}): Promise<any> {
  const qs = buildQuery({
    limit: args?.limit ?? 200,
    offset: args?.offset ?? 0,
    org_unit_id: args?.org_unit_id,
  });
  return apiGetJson<any>("/directory/positions", qs);
}

/**
 * Отделы
 */
export async function getDepartments(args?: { limit?: number; offset?: number }): Promise<any> {
  const qs = buildQuery({
    limit: args?.limit ?? 200,
    offset: args?.offset ?? 0,
  });
  return apiGetJson<any>("/directory/departments", qs);
}