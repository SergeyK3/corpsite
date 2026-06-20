// FILE: corpsite-ui/app/admin/system/_lib/adminSystemApi.client.ts
import { apiFetchJson } from "@/lib/api";
import { formatThrownError } from "@/lib/i18n";

/* ---------- Users ---------- */

export type AdminUser = {
  user_id: number;
  employee_id?: number | null;
  full_name?: string | null;
  login?: string | null;
  role_id?: number | null;
  role_name?: string | null;
  unit_id?: number | null;
  is_active?: boolean;
  must_change_password?: boolean;
  locked_at?: string | null;
  locked_reason?: string | null;
  token_version?: number;
  created_at?: string | null;
  audit_id?: number;
};

/* ---------- Access ---------- */

export type AccessGrant = {
  grant_id: number;
  access_role_id?: number;
  access_role_code?: string;
  access_level?: string;
  level_rank?: number;
  target_type: string;
  target_id: number;
  resource_key?: string;
  scope_type?: string;
  scope_id?: number | null;
  include_subtree?: boolean;
  starts_at?: string | null;
  ends_at?: string | null;
  active_flag?: boolean;
  granted_by_user_id?: number | null;
  reason?: string | null;
  created_at?: string | null;
  revoked_at?: string | null;
  revoked_by_user_id?: number | null;
};

export type AccessGrantCreate = {
  access_role_id: number;
  target_type: string;
  target_id: number;
  resource_key?: string;
  scope_type?: string;
  scope_id?: number | null;
  include_subtree?: boolean;
  reason?: string;
};

export type EffectiveAccess = {
  user_id?: number;
  person_id?: number | null;
  employee_id?: number | null;
  effective_role_code: string;
  access_level: string;
  level_rank: number;
  matched_grants?: Record<string, unknown>[];
  deny_grants?: Record<string, unknown>[];
  explanation?: Record<string, unknown>;
};

export type Paginated<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};

/* ---------- Enrollment ---------- */

export type EnrollmentQueueItem = {
  queue_id: number;
  person_id?: number | null;
  assignment_id?: number | null;
  change_event_id?: number | null;
  queue_status: string;
  reason: string;
  detected_at?: string | null;
  resolved_at?: string | null;
  resolved_by_user_id?: number | null;
  decision_comment?: string | null;
  idempotency_key?: string | null;
};

export type EnrollmentDetectResult = {
  dry_run: boolean;
  candidate_count?: number;
  candidates?: Record<string, unknown>[];
  enqueued?: Record<string, unknown>[];
};

export type EnrollmentApplyResult = {
  queue_id: number;
  queue_status: string;
  person_id?: number;
  assignment_id?: number;
  employee_id?: number;
  link_id?: number;
  created_employee?: boolean;
  already_applied?: boolean;
};

/* ---------- Assignments ---------- */

export type AssignmentDriftItem = {
  employee_id: number;
  person_id?: number | null;
  assignment_id?: number | null;
  has_primary_assignment?: boolean;
  has_drift?: boolean;
  diff?: Record<string, { employee?: unknown; assignment?: unknown }>;
};

export type ReconcileResult = {
  employee_id: number;
  dry_run?: boolean;
  applied?: boolean;
  has_drift?: boolean;
  diff?: Record<string, unknown>;
  would_update?: Record<string, unknown>;
  reason?: string;
};

/* ---------- Security audit ---------- */

export type SecurityAuditEvent = {
  audit_id: number;
  event_type: string;
  happened_at?: string | null;
  actor_user_id?: number | null;
  target_user_id?: number | null;
  target_person_id?: number | null;
  target_employee_id?: number | null;
  success?: boolean;
  failure_reason?: string | null;
  metadata?: Record<string, unknown>;
};

export type AccessRoleRef = {
  access_role_id: number;
  code: string;
  label: string;
  description?: string | null;
  access_level?: string | null;
  level_rank?: number | null;
  active_flag?: boolean;
};

export type AccessTargetSearchItem = {
  target_type: string;
  target_id: number;
  label?: string | null;
  subtitle?: string | null;
  metadata?: Record<string, unknown>;
};

export type GuardModeInfo = {
  guard_mode: string;
  message: string;
  enforcement_active?: boolean;
  shadow_mode?: boolean;
};

export function formatAccessRoleLabel(role: AccessRoleRef): string {
  const code = role.code || "";
  const name = role.label || code;
  const level = role.access_level ? ` — ${role.access_level}` : "";
  return `${name}${level} [${code}]`;
}

export async function fetchAccessRoles(): Promise<AccessRoleRef[]> {
  return apiFetchJson<AccessRoleRef[]>("/admin/access/roles");
}

export async function fetchGuardMode(): Promise<GuardModeInfo> {
  return apiFetchJson<GuardModeInfo>("/admin/access/guard-mode");
}

export async function searchAccessTargets(params: {
  target_type: string;
  q?: string;
  limit?: number;
}): Promise<{ items: AccessTargetSearchItem[] }> {
  return apiFetchJson<{ items: AccessTargetSearchItem[] }>("/admin/access/targets/search", {
    query: {
      target_type: params.target_type,
      q: params.q ?? "",
      limit: params.limit ?? 20,
    },
  });
}

export function mapAdminSystemApiError(err: unknown, fallback: string): string {
  return formatThrownError(err, { fallback });
}

export async function fetchAdminUsers(params?: {
  limit?: number;
  offset?: number;
}): Promise<AdminUser[]> {
  return apiFetchJson<AdminUser[]>("/admin/users", { query: params });
}

export async function fetchAdminUser(userId: number): Promise<AdminUser> {
  return apiFetchJson<AdminUser>(`/admin/users/${userId}`);
}

export async function lockAdminUser(userId: number, reason = "admin"): Promise<AdminUser> {
  return apiFetchJson<AdminUser>(`/admin/users/${userId}/lock`, {
    method: "POST",
    query: { reason },
  });
}

export async function unlockAdminUser(userId: number): Promise<AdminUser> {
  return apiFetchJson<AdminUser>(`/admin/users/${userId}/unlock`, { method: "POST" });
}

export async function forcePasswordChangeAdminUser(userId: number): Promise<AdminUser> {
  return apiFetchJson<AdminUser>(`/admin/users/${userId}/force-password-change`, {
    method: "POST",
  });
}

export async function fetchEffectiveAccessList(params?: {
  limit?: number;
  offset?: number;
}): Promise<EffectiveAccess[]> {
  return apiFetchJson<EffectiveAccess[]>("/admin/access/effective", { query: params });
}

export async function fetchEffectiveAccessUser(userId: number): Promise<EffectiveAccess> {
  return apiFetchJson<EffectiveAccess>(`/admin/access/effective/${userId}`);
}

export async function fetchAccessGrants(params?: {
  target_type?: string;
  target_id?: number;
  active_only?: boolean;
  limit?: number;
  offset?: number;
}): Promise<Paginated<AccessGrant>> {
  return apiFetchJson<Paginated<AccessGrant>>("/admin/access/grants", { query: params });
}

export async function createAccessGrant(body: AccessGrantCreate): Promise<AccessGrant> {
  return apiFetchJson<AccessGrant>("/admin/access/grants", { method: "POST", body });
}

export async function revokeAccessGrant(grantId: number, reason?: string): Promise<AccessGrant> {
  return apiFetchJson<AccessGrant>(`/admin/access/grants/${grantId}`, {
    method: "DELETE",
    query: reason ? { reason } : undefined,
  });
}

export async function fetchEnrollmentQueue(params?: {
  queue_status?: string;
  limit?: number;
  offset?: number;
}): Promise<Paginated<EnrollmentQueueItem>> {
  return apiFetchJson<Paginated<EnrollmentQueueItem>>("/admin/enrollment/queue", { query: params });
}

export async function detectEnrollment(params?: {
  batch_id?: number;
  dry_run?: boolean;
  limit?: number;
}): Promise<EnrollmentDetectResult> {
  return apiFetchJson<EnrollmentDetectResult>("/admin/enrollment/detect", {
    method: "POST",
    body: {
      batch_id: params?.batch_id ?? null,
      dry_run: params?.dry_run ?? false,
      limit: params?.limit ?? 500,
    },
  });
}

export async function approveEnrollmentQueueItem(
  queueId: number,
  comment?: string,
): Promise<EnrollmentQueueItem> {
  return apiFetchJson<EnrollmentQueueItem>(`/admin/enrollment/queue/${queueId}/approve`, {
    method: "POST",
    body: { comment: comment ?? null },
  });
}

export async function rejectEnrollmentQueueItem(
  queueId: number,
  comment?: string,
): Promise<EnrollmentQueueItem> {
  return apiFetchJson<EnrollmentQueueItem>(`/admin/enrollment/queue/${queueId}/reject`, {
    method: "POST",
    body: { comment: comment ?? null },
  });
}

export async function applyEnrollmentQueueItem(queueId: number): Promise<EnrollmentApplyResult> {
  return apiFetchJson<EnrollmentApplyResult>(`/admin/enrollment/queue/${queueId}/apply`, {
    method: "POST",
  });
}

export async function fetchAssignmentDrift(params?: {
  limit?: number;
  offset?: number;
}): Promise<Paginated<AssignmentDriftItem>> {
  return apiFetchJson<Paginated<AssignmentDriftItem>>("/admin/assignments/drift", {
    query: params,
  });
}

export async function reconcileAssignment(
  employeeId: number,
  dryRun: boolean,
): Promise<ReconcileResult> {
  return apiFetchJson<ReconcileResult>(`/admin/assignments/reconcile/${employeeId}`, {
    method: "POST",
    query: { dry_run: dryRun },
  });
}

export async function fetchSecurityAudit(params?: {
  event_type?: string;
  actor_user_id?: number;
  target_user_id?: number;
  target_person_id?: number;
  target_employee_id?: number;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}): Promise<Paginated<SecurityAuditEvent>> {
  return apiFetchJson<Paginated<SecurityAuditEvent>>("/admin/security-audit", { query: params });
}
