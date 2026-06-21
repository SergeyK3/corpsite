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
  previous_diff?: Record<string, { employee?: unknown; assignment?: unknown }>;
  assignment_id?: number | null;
  reason?: string;
};

/* ---------- Security audit ---------- */

export type SecurityAuditEvent = {
  audit_id: number;
  event_type: string;
  happened_at?: string | null;
  actor_user_id?: number | null;
  actor_login?: string | null;
  actor_label?: string | null;
  target_user_id?: number | null;
  target_user_login?: string | null;
  target_user_label?: string | null;
  target_person_id?: number | null;
  target_person_label?: string | null;
  target_employee_id?: number | null;
  target_employee_label?: string | null;
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

export type BulkReconcileResult = {
  dry_run: boolean;
  total_drift: number;
  processed: number;
  applied_count: number;
  with_drift: number;
  results: ReconcileResult[];
};

export type BulkEnrollmentResult = {
  processed: number;
  succeeded: number;
  failed: number;
  items: EnrollmentQueueItem[];
  errors: { queue_id: number; error: string }[];
};

export type EnrollmentExplain = EnrollmentQueueItem & {
  explanation?: {
    steps?: string[];
    reason_label?: string;
    person?: { person_id?: number; full_name?: string; iin?: string };
    assignment?: {
      assignment_id?: number;
      org_unit_id?: number;
      org_unit_name?: string;
      position_id?: number;
      position_name?: string;
    };
    source?: { change_event_id?: number; change_event_type?: string };
  };
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

export async function reconcileAssignmentsBulk(params: {
  employee_ids?: number[];
  all_drift?: boolean;
  dry_run?: boolean;
  limit?: number;
}): Promise<BulkReconcileResult> {
  return apiFetchJson<BulkReconcileResult>("/admin/assignments/reconcile/bulk", {
    method: "POST",
    body: {
      employee_ids: params.employee_ids ?? [],
      all_drift: params.all_drift ?? false,
      dry_run: params.dry_run ?? true,
      limit: params.limit ?? 500,
    },
  });
}

export async function approveEnrollmentBulk(
  queueIds: number[],
  comment?: string,
): Promise<BulkEnrollmentResult> {
  return apiFetchJson<BulkEnrollmentResult>("/admin/enrollment/approve/bulk", {
    method: "POST",
    body: { queue_ids: queueIds, comment: comment ?? null },
  });
}

export async function rejectEnrollmentBulk(
  queueIds: number[],
  comment?: string,
): Promise<BulkEnrollmentResult> {
  return apiFetchJson<BulkEnrollmentResult>("/admin/enrollment/reject/bulk", {
    method: "POST",
    body: { queue_ids: queueIds, comment: comment ?? null },
  });
}

export async function fetchEnrollmentExplain(queueId: number): Promise<EnrollmentExplain> {
  return apiFetchJson<EnrollmentExplain>(`/admin/enrollment/queue/${queueId}/explain`);
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

/* ---------- Personnel visibility (ADR-042 E1) ---------- */

export type PersonnelVisibilityAssignment = {
  assignment_id: number;
  target_type: string;
  target_user_id?: number | null;
  target_position_id?: number | null;
  target_department_id?: number | null;
  scope_type: string;
  scope_department_id?: number | null;
  scope_department_group_id?: number | null;
  can_view_personnel: boolean;
  can_view_tasks: boolean;
  is_active: boolean;
  created_at?: string | null;
  created_by_user_id?: number | null;
  revoked_at?: string | null;
  revoked_by_user_id?: number | null;
  revoke_reason?: string | null;
};

export type PersonnelVisibilityCreate = {
  target_type: string;
  target_user_id?: number | null;
  target_position_id?: number | null;
  target_department_id?: number | null;
  scope_type: string;
  scope_department_id?: number | null;
  scope_department_group_id?: number | null;
  can_view_personnel?: boolean;
  can_view_tasks?: boolean;
};

export type EffectivePersonnelVisibility = {
  has_visibility: boolean;
  show_org_sidebar: boolean;
  organization_wide: boolean;
  scope_unit_ids?: number[] | null;
  can_view_personnel: boolean;
  can_view_tasks: boolean;
  source: string;
  matched_assignment_ids?: number[];
  implicit_from_access_level?: boolean;
};

export async function fetchPersonnelVisibilityAssignments(params?: {
  active_only?: boolean;
  limit?: number;
  offset?: number;
}): Promise<Paginated<PersonnelVisibilityAssignment>> {
  return apiFetchJson<Paginated<PersonnelVisibilityAssignment>>(
    "/admin/personnel/visibility/assignments",
    { query: params },
  );
}

export async function createPersonnelVisibilityAssignment(
  body: PersonnelVisibilityCreate,
): Promise<PersonnelVisibilityAssignment> {
  return apiFetchJson<PersonnelVisibilityAssignment>("/admin/personnel/visibility/assignments", {
    method: "POST",
    body,
  });
}

export async function revokePersonnelVisibilityAssignment(
  assignmentId: number,
  reason?: string,
): Promise<PersonnelVisibilityAssignment> {
  return apiFetchJson<PersonnelVisibilityAssignment>(
    `/admin/personnel/visibility/assignments/${assignmentId}/revoke`,
    { method: "POST", body: { reason: reason ?? null } },
  );
}

export async function fetchEffectivePersonnelVisibility(
  userId: number,
): Promise<EffectivePersonnelVisibility> {
  return apiFetchJson<EffectivePersonnelVisibility>("/admin/personnel/visibility/effective", {
    query: { user_id: userId },
  });
}
