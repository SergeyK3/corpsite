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
  EmployeeTerminationVerifyPayload,
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
 * Р•РґРёРЅР°СЏ РјР°РїР° РѕС€РёР±РѕРє fetch/HTTP в†’ С‡РµР»РѕРІРµРєРѕ-С‡РёС‚Р°РµРјС‹Р№ С‚РµРєСЃС‚ РґР»СЏ UI.
 * Р’Р°Р¶РЅРѕ: СЌРєСЃРїРѕСЂС‚РёСЂСѓРµС‚СЃСЏ Рё РёСЃРїРѕР»СЊР·СѓРµС‚СЃСЏ РІ РєРѕРјРїРѕРЅРµРЅС‚Р°С….
 */
export function mapApiErrorToMessage(e: unknown, fallback = "РћС€РёР±РєР° Р·Р°РїСЂРѕСЃР°."): string {
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

async function apiDeleteJson<T>(path: string): Promise<T> {
  const res = await fetch(resolveApiUrl(path), {
    method: "DELETE",
    headers: apiAuthHeaders(),
    cache: "no-store",
  });

  if (!res.ok) {
    const t = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status}: ${t || res.statusText}`);
  }

  if (res.status === 204) {
    return {} as T;
  }

  return (await res.json()) as T;
}

/**
 * РЎРїРёСЃРѕРє СЃРѕС‚СЂСѓРґРЅРёРєРѕРІ
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
  sort?: string | null;
  order?: string | null;
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
    sort: args.sort ?? undefined,
    order: args.order ?? undefined,
  });

  return apiGetJson<EmployeesResponse>("/directory/employees", qs);
}

/**
 * Р”РµС‚Р°Р»Рё СЃРѕС‚СЂСѓРґРЅРёРєР°
 */
export async function getEmployee(employeeId: string): Promise<EmployeeDetails> {
  const id = String(employeeId).trim();
  if (!id) throw new Error("Employee id is empty");
  return apiGetJson<EmployeeDetails>(`/directory/employees/${encodeURIComponent(id)}`);
}

/**
 * Р—Р°РІРµСЂС€РµРЅРёРµ СЂР°Р±РѕС‚С‹ СЃРѕС‚СЂСѓРґРЅРёРєР°
 * Backend: POST /directory/employees/{id}/terminate
 *
 * РЎРѕРІРјРµСЃС‚РёРјРѕСЃС‚СЊ СЃ UI:
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

export type EmployeeHardDeleteResponse = {
  ok: boolean;
  employee_id: number;
  full_name?: string;
  person_id?: number | null;
  person_deleted?: boolean;
};

export type EmployeeBulkDeleteDeletedItem = {
  employee_id: number;
  full_name?: string;
  person_id?: number | null;
  person_deleted?: boolean;
};

export type EmployeeBulkDeleteFailedItem = {
  employee_id: number;
  error_code: string;
  message: string;
};

export type EmployeeBulkDeleteResponse = {
  requested: number;
  deleted: EmployeeBulkDeleteDeletedItem[];
  failed: EmployeeBulkDeleteFailedItem[];
};

/**
 * РђРґРјРёРЅРёСЃС‚СЂР°С‚РёРІРЅРѕРµ hard-delete СЃРѕС‚СЂСѓРґРЅРёРєР° (С‚РѕР»СЊРєРѕ СЃРёСЃС‚РµРјРЅС‹Р№ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂ).
 * Backend: DELETE /directory/employees/{id}
 */
export async function deleteEmployee(employeeId: string): Promise<EmployeeHardDeleteResponse> {
  const id = String(employeeId).trim();
  if (!id) throw new Error("Employee id is empty");
  return apiDeleteJson<EmployeeHardDeleteResponse>(`/directory/employees/${encodeURIComponent(id)}`);
}

/**
 * РњР°СЃСЃРѕРІРѕРµ hard-delete СЃРѕС‚СЂСѓРґРЅРёРєРѕРІ (С‚РѕР»СЊРєРѕ СЃРёСЃС‚РµРјРЅС‹Р№ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂ).
 * Backend: POST /directory/employees/bulk-delete
 */
export async function bulkDeleteEmployees(
  employeeIds: number[],
): Promise<EmployeeBulkDeleteResponse> {
  const ids = Array.from(
    new Set(
      employeeIds
        .map((id) => Number(id))
        .filter((id) => Number.isFinite(id) && id > 0),
    ),
  );
  if (ids.length === 0) throw new Error("employee_ids is empty");
  return apiPostJson<EmployeeBulkDeleteResponse>("/directory/employees/bulk-delete", {
    employee_ids: ids,
  });
}

/**
 * РЎРѕР·РґР°РЅРёРµ СЃРѕС‚СЂСѓРґРЅРёРєР°
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
 * Р РµРґР°РєС‚РёСЂРѕРІР°РЅРёРµ СЃРѕС‚СЂСѓРґРЅРёРєР°
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
 * РљР°РґСЂРѕРІС‹Р№ РїРµСЂРµРІРѕРґ СЃРѕС‚СЂСѓРґРЅРёРєР°
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
 * РђРґРјРёРЅРёСЃС‚СЂР°С‚РёРІРЅР°СЏ РєРѕСЂСЂРµРєС‚РёСЂРѕРІРєР° РґР°РЅРЅС‹С… СЃРѕС‚СЂСѓРґРЅРёРєР° (audited).
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


  const isCombined = body.domain === "combined";
  const org_unit_id = body.org_unit_id == null ? null : Number(body.org_unit_id);
  if (
    !isCombined &&
    (org_unit_id === null || !Number.isFinite(org_unit_id) || org_unit_id < 1)
  ) {
    throw new Error("org_unit_id is required");
  }

  const payload: Record<string, unknown> = {
    domain: body.domain,
    effective_date,
    reason,
    comment,
  };

  if (org_unit_id != null && Number.isFinite(org_unit_id) && org_unit_id >= 1) {
    payload.org_unit_id = org_unit_id;
  }

  if ("date_from" in body) payload.date_from = body.date_from;
  if ("date_to" in body) payload.date_to = body.date_to;

  if (body.position_id != null && Number.isFinite(Number(body.position_id))) {
    payload.position_id = Number(body.position_id);
  }

  if (body.employment_rate != null && Number.isFinite(Number(body.employment_rate))) {
    payload.employment_rate = Number(body.employment_rate);
  }

  if (body.status != null) {
    payload.status = body.status;
  }

  if (isCombined && body.full_name != null) {
    payload.full_name = body.full_name;
  }

  return apiPostJson<EmployeeCorrectResponse>(
    `/directory/employees/${encodeURIComponent(id)}/correct`,
    payload
  );
}

/**
 * РљР°РґСЂРѕРІР°СЏ РёСЃС‚РѕСЂРёСЏ СЃРѕС‚СЂСѓРґРЅРёРєР°
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
 * РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ РїРѕ employee_id
 * Backend: GET /directory/users?employee_id=
 */
export async function getUserByEmployeeId(employeeId: number | string): Promise<UserDTO> {
  const id = Number(employeeId);
  if (!Number.isFinite(id) || id < 1) throw new Error("employee_id is required");
  const qs = buildQuery({ employee_id: id });
  return apiGetJson<UserDTO>("/directory/users", qs);
}

/**
 * РЎРѕР·РґР°РЅРёРµ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ РґР»СЏ СЃРѕС‚СЂСѓРґРЅРёРєР°
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
 * РР·РјРµРЅРµРЅРёРµ Role Corpsite Сѓ СЃСѓС‰РµСЃС‚РІСѓСЋС‰РµРіРѕ Platform User (Р±РµР· РїРµСЂРµСЃРѕР·РґР°РЅРёСЏ Р°РєРєР°СѓРЅС‚Р°).
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
 * Р РѕР»Рё (РґР»СЏ select РїСЂРё СЃРѕР·РґР°РЅРёРё РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ)
 */
export async function getRoles(args?: { limit?: number; offset?: number }): Promise<any> {
  const qs = buildQuery({
    limit: args?.limit ?? 200,
    offset: args?.offset ?? 0,
  });
  return apiGetJson<any>("/directory/roles", qs);
}

/**
 * Р”РѕР»Р¶РЅРѕСЃС‚Рё
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
 * РћС‚РґРµР»С‹
 */
export async function getDepartments(args?: { limit?: number; offset?: number }): Promise<any> {
  const qs = buildQuery({
    limit: args?.limit ?? 200,
    offset: args?.offset ?? 0,
  });
  return apiGetJson<any>("/directory/departments", qs);
}

export async function verifyEmployeeTermination(
  employeeId: string,
  payload: EmployeeTerminationVerifyPayload,
): Promise<EmployeeDetails> {
  const id = String(employeeId).trim();
  if (!id) throw new Error("Employee id is empty");
  return apiPatchJson<EmployeeDetails>(
    `/directory/employees/${encodeURIComponent(id)}/termination-verification`,
    payload,
  );
}
