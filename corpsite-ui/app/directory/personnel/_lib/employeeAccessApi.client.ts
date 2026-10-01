import { buildHeaders, handleAuthFailureIfNeeded, readJsonSafe, toApiError } from "@/lib/api";
import { resolveApiUrl } from "@/lib/apiBase";

export type EmployeeAccessState = {
  employee_id: number;
  person_id: number;
  user_id: number;
  has_linked_user: boolean;
  employee_is_active: boolean;
  is_active: boolean;
  must_change_password: boolean;
  lock_active: boolean;
  lock_reason: string | null;
  automatic_lock_active: boolean;
  locked_until: string | null;
  token_version: number;
  has_active_assignment: boolean;
  generated_at: string;
};

export type EmployeeTerminationPreview = {
  employee_id: number;
  person_id: number | null;
  user_id: number | null;
  linkage_state: string;
  has_linked_user: boolean;
  employee_is_active: boolean;
  has_active_assignment: boolean;
  has_applied_approved_termination_event: boolean | null;
  counts: {
    unfinished_personal_tasks: number | null;
    active_personal_approvals: number | null;
    active_incoming_document_assignments: number | null;
    pending_notifications_deliveries: number | null;
    active_direct_grants_by_target_type: Record<string, number | null>;
    dependency_status: Record<string, "available" | "unavailable">;
  };
  warnings: string[];
  generated_at: string;
};

export type EmployeePasswordReset = {
  employee_id: number;
  user_id: number;
  temporary_password: string;
  must_change_password: boolean;
  temp_password_expires_at: string;
  token_version: number;
  brute_force_lock_cleared: boolean;
};

function devHeaders(): Record<string, string> {
  const appEnv = (process.env.NEXT_PUBLIC_APP_ENV || "dev").trim().toLowerCase();
  const userId = (process.env.NEXT_PUBLIC_DEV_X_USER_ID || "").trim();
  const headers: Record<string, string> = { Accept: "application/json" };
  if (userId && appEnv !== "prod" && appEnv !== "production") headers["X-User-Id"] = userId;
  return buildHeaders(headers) as Record<string, string>;
}

async function employeeAccessGet<T>(path: string, options?: { signal?: AbortSignal }): Promise<T> {
  const response = await fetch(resolveApiUrl(path), {
    method: "GET",
    headers: devHeaders(),
    cache: "no-store",
    signal: options?.signal,
  });
  const body = await readJsonSafe(response);
  if (!response.ok) {
    handleAuthFailureIfNeeded(response.status, body);
    throw toApiError(response.status, body, { method: "GET", url: path });
  }
  return body as T;
}

export function getEmployeeAccessState(employeeId: string | number, options?: { signal?: AbortSignal }) {
  return employeeAccessGet<EmployeeAccessState>(
    `/directory/personnel/employees/${encodeURIComponent(String(employeeId))}/access`, options,
  );
}

export function getEmployeeTerminationPreview(employeeId: string | number, options?: { signal?: AbortSignal }) {
  return employeeAccessGet<EmployeeTerminationPreview>(
    `/directory/personnel/employees/${encodeURIComponent(String(employeeId))}/access/termination-preview`, options,
  );
}

export async function resetEmployeePassword(employeeId: string | number): Promise<EmployeePasswordReset> {
  const path = `/directory/personnel/employees/${encodeURIComponent(String(employeeId))}/access/password-reset`;
  const response = await fetch(resolveApiUrl(path), {
    method: "POST",
    headers: devHeaders(),
    cache: "no-store",
  });
  const body = await readJsonSafe(response);
  if (!response.ok) {
    handleAuthFailureIfNeeded(response.status, body);
    throw toApiError(response.status, body, { method: "POST", url: path });
  }
  return body as EmployeePasswordReset;
}
