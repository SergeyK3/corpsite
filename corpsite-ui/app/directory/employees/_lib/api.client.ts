// FILE: corpsite-ui/app/directory/employees/_lib/api.client.ts

import type {
  EmployeesResponse,
  EmployeeDetails,
  EmployeeCreatePayload,
  EmployeeUpdatePayload,
  EmployeeTransferPayload,
  EmployeeTransferResponse,
  EmployeeCorrectPayload,
  EmployeeCorrectResponse,
  EmployeeEventsResponse,
  UserDTO,
  UserCreatePayload,
} from "./types";
import { buildHeaders } from "@/lib/api";
import { formatThrownError } from "@/lib/i18n";
import { resolveApiUrl } from "@/lib/apiBase";

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

function apiAuthHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const headers: Record<string, string> = { Accept: "application/json", ...extra };
  const devUserId = getDevUserId();
  if (devUserId) headers["X-User-Id"] = devUserId;
  return buildHeaders(headers) as Record<string, string>;
}

async function apiGetJson<T>(path: string, qs?: string): Promise<T> {
  const url = qs ? `${resolveApiUrl(path)}?${qs}` : resolveApiUrl(path);

  const res = await fetch(url, {
    method: "GET",
    headers: apiAuthHeaders(),
    cache: "no-store",
  });

  if (!res.ok) {
    const t = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status}: ${t || res.statusText}`);
  }

  return (await res.json()) as T;
}

async function apiPostJson<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(resolveApiUrl(path), {
    method: "POST",
    headers: apiAuthHeaders({ "Content-Type": "application/json" }),
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
  const res = await fetch(resolveApiUrl(path), {
    method: "PATCH",
    headers: apiAuthHeaders({ "Content-Type": "application/json" }),
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
  include_applicants?: boolean;
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
    include_applicants: args.include_applicants ? "true" : undefined,
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

  if (Object.keys(payload).length === 0) {
    throw new Error("At least one field is required");
  }

  return apiPatchJson<EmployeeDetails>(`/directory/employees/${encodeURIComponent(id)}`, payload);
}

/**
 * Кадровый перевод сотрудника
 * Backend: POST /directory/employees/{id}/transfer
 */
export async function transferEmployee(
  employeeId: string,
  body: EmployeeTransferPayload
): Promise<EmployeeTransferResponse> {
  const id = String(employeeId).trim();
  if (!id) throw new Error("Employee id is empty");

  const to_org_unit_id = Number(body.to_org_unit_id);
  if (!Number.isFinite(to_org_unit_id) || to_org_unit_id < 1) {
    throw new Error("to_org_unit_id is required");
  }

  const effective_date = String(body.effective_date ?? "").trim();
  if (!effective_date) throw new Error("effective_date is required");

  const payload: Record<string, unknown> = {
    to_org_unit_id,
    effective_date,
  };

  if (body.to_position_id != null && Number.isFinite(Number(body.to_position_id))) {
    payload.to_position_id = Number(body.to_position_id);
  }

  if (body.to_employment_rate != null && Number.isFinite(Number(body.to_employment_rate))) {
    payload.to_employment_rate = Number(body.to_employment_rate);
  }

  const orderRef = String(body.order_ref ?? "").trim();
  if (orderRef) payload.order_ref = orderRef;

  const comment = String(body.comment ?? "").trim();
  if (comment) payload.comment = comment;

  return apiPostJson<EmployeeTransferResponse>(
    `/directory/employees/${encodeURIComponent(id)}/transfer`,
    payload
  );
}

/**
 * Административная корректировка данных сотрудника (audited).
 * Backend: POST /directory/employees/{id}/correct
 */
export async function correctEmployee(
  employeeId: string,
  body: EmployeeCorrectPayload
): Promise<EmployeeCorrectResponse> {
  const id = String(employeeId).trim();
  if (!id) throw new Error("Employee id is empty");

  const effective_date = String(body.effective_date ?? "").trim();
  if (!effective_date) throw new Error("effective_date is required");

  const reason = String(body.reason ?? "").trim();
  if (!reason) throw new Error("reason is required");

  const comment = String(body.comment ?? "").trim();
  if (!comment) throw new Error("comment is required");

  if (body.domain === "general") {
    const full_name = String(body.full_name ?? "").trim();
    if (!full_name) throw new Error("full_name is required");

    return apiPostJson<EmployeeCorrectResponse>(
      `/directory/employees/${encodeURIComponent(id)}/correct`,
      {
        domain: "general",
        full_name,
        effective_date,
        reason,
        comment,
      }
    );
  }

  const org_unit_id = Number(body.org_unit_id);
  if (!Number.isFinite(org_unit_id) || org_unit_id < 1) {
    throw new Error("org_unit_id is required");
  }

  const payload: Record<string, unknown> = {
    domain: "assignment",
    org_unit_id,
    date_from: body.date_from ?? null,
    date_to: body.date_to ?? null,
    effective_date,
    reason,
    comment,
  };

  if (body.position_id != null && Number.isFinite(Number(body.position_id))) {
    payload.position_id = Number(body.position_id);
  }

  if (body.employment_rate != null && Number.isFinite(Number(body.employment_rate))) {
    payload.employment_rate = Number(body.employment_rate);
  }

  return apiPostJson<EmployeeCorrectResponse>(
    `/directory/employees/${encodeURIComponent(id)}/correct`,
    payload
  );
}

/**
 * Кадровая история сотрудника
 * Backend: GET /directory/employees/{id}/events
 */
export async function listEmployeeEvents(
  employeeId: string,
  args?: {
    event_type?: string;
    limit?: number;
    offset?: number;
  }
): Promise<EmployeeEventsResponse> {
  const id = String(employeeId).trim();
  if (!id) throw new Error("Employee id is empty");

  const qs = buildQuery({
    event_type: args?.event_type,
    limit: args?.limit ?? 50,
    offset: args?.offset ?? 0,
  });

  return apiGetJson<EmployeeEventsResponse>(
    `/directory/employees/${encodeURIComponent(id)}/events`,
    qs
  );
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
 * Изменение Role Corpsite у существующего Platform User (без пересоздания аккаунта).
 * Backend: PATCH /directory/users/{user_id}/role
 */
export async function updateUserRole(userId: number | string, roleId: number | string): Promise<UserDTO> {
  const uid = Number(userId);
  const rid = Number(roleId);
  if (!Number.isFinite(uid) || uid < 1) throw new Error("user_id is required");
  if (!Number.isFinite(rid) || rid < 1) throw new Error("role_id is required");
  return apiPatchJson<UserDTO>(`/directory/users/${uid}/role`, { role_id: rid });
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
  org_group_id?: number;
  scope?: "used" | "allowed";
}): Promise<any> {
  const qs = buildQuery({
    limit: args?.limit ?? 200,
    offset: args?.offset ?? 0,
    org_unit_id: args?.org_unit_id,
    org_group_id: args?.org_group_id,
    scope: args?.scope,
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