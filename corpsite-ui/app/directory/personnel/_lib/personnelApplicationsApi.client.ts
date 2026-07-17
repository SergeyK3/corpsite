import { buildHeaders, readJsonSafe, toApiError } from "@/lib/api";
import { formatThrownError } from "@/lib/i18n";
import { resolveApiUrl } from "@/lib/apiBase";

export const PERSONNEL_APPLICATIONS_BASE_PATH = "/directory/personnel-applications";

export type PersonnelApplicationPreviewResponse = {
  iin: string;
  person_exists: boolean;
  person_id: number | null;
  full_name: string | null;
  hr_relationship_context: string | null;
  has_active_employee: boolean;
  has_active_application: boolean;
  active_application_id: number | null;
  can_register: boolean;
  block_reason: string | null;
};

export type PersonnelApplicationRegisterResponse = {
  person_id: number;
  application_id: number;
  action: "created" | "opened_existing";
  card_href: string;
};

export type PersonnelApplicationDetail = {
  application_id: number;
  person_id: number;
  full_name?: string | null;
  iin?: string | null;
  status: string;
  application_received_at: string;
  application_source: string;
  vacancy_check_status: string;
  vacancy_checked_at?: string | null;
  vacancy_checked_by_user_id?: number | null;
  intended_org_group_id?: number | null;
  intended_org_unit_id?: number | null;
  intended_position_id?: number | null;
  intended_org_group_name?: string | null;
  intended_org_unit_name?: string | null;
  intended_position_name?: string | null;
  intended_employment_rate?: number | string | null;
  intended_vacancy_text?: string | null;
  contact_mobile_phone?: string | null;
  contact_email?: string | null;
  director_resolution_status?: string | null;
  director_resolution_at?: string | null;
  director_resolution_by_user_id?: number | null;
  director_resolution_note?: string | null;
  personnel_order_id?: number | null;
  registered_at: string;
  registered_by_user_id: number;
  registered_by_name?: string | null;
  hr_note?: string | null;
  idempotency_key?: string | null;
  created_at: string;
  updated_at: string;
  intake_link_status?: string | null;
  intake_draft_status?: string | null;
  intake_opened_at?: string | null;
  intake_submitted_at?: string | null;
  employee_id?: number | null;
  employee_full_name?: string | null;
  employee_created_at?: string | null;
  personnel_order_number?: string | null;
  personnel_order_date?: string | null;
  hire_applied_at?: string | null;
  completed_at?: string | null;
  closed_at?: string | null;
  cancel_reason?: string | null;
  cancelled_by_user_id?: number | null;
  closed_by_user_id?: number | null;
  is_read_only?: boolean;
};

export type PersonnelApplicationListItem = {
  application_id: number;
  person_id: number;
  full_name: string | null;
  iin: string | null;
  status: string;
  application_received_at: string;
  intended_org_group_id: number | null;
  intended_org_unit_id: number | null;
  intended_position_id: number | null;
  intended_org_group_name: string | null;
  intended_org_unit_name: string | null;
  intended_position_name: string | null;
  registered_at: string;
  registered_by_user_id: number;
  registered_by_name: string | null;
  director_resolution_status: string | null;
  personnel_order_id: number | null;
  is_active: boolean;
  intake_link_status: string | null;
  intake_draft_status: string | null;
  intake_opened_at: string | null;
  intake_submitted_at: string | null;
  employee_id: number | null;
  employee_full_name: string | null;
  completed_at: string | null;
  closed_at: string | null;
  is_read_only: boolean;
};

export type PersonnelApplicationListResponse = {
  items: PersonnelApplicationListItem[];
  total: number;
  limit: number;
  offset: number;
};

export type PersonnelApplicationHistoryResponse = {
  person_id: number;
  items: PersonnelApplicationDetail[];
};

export type PersonnelApplicationListFilters = {
  q?: string;
  status?: string;
  view?: "active" | "archive";
  org_group_id?: number;
  org_unit_id?: number;
  position_id?: number;
  sort?: string;
  limit?: number;
  offset?: number;
};

export type PersonnelApplicationRegisterBody = {
  iin: string;
  full_name?: string | null;
  birth_date?: string | null;
  application_received_at: string;
  vacancy_check_status?: string;
  intended_org_group_id?: number | null;
  intended_org_unit_id?: number | null;
  intended_position_id?: number | null;
  intended_employment_rate?: number | null;
  intended_vacancy_text?: string | null;
  contact_mobile_phone?: string | null;
  contact_email?: string | null;
  hr_note?: string | null;
  idempotency_key?: string | null;
};

function getDevUserId(): string | null {
  const appEnv = (process.env.NEXT_PUBLIC_APP_ENV || "dev").trim().toLowerCase();
  if (appEnv === "prod" || appEnv === "production") return null;
  const v = (process.env.NEXT_PUBLIC_DEV_X_USER_ID || "").trim();
  return v ? v : null;
}

function authHeaders(json = false): Record<string, string> {
  const extra: Record<string, string> = { Accept: "application/json" };
  if (json) extra["Content-Type"] = "application/json";
  const devUserId = getDevUserId();
  if (devUserId) extra["X-User-Id"] = devUserId;
  return buildHeaders(extra) as Record<string, string>;
}

function buildQuery(filters: PersonnelApplicationListFilters): string {
  const params = new URLSearchParams();
  if (filters.q?.trim()) params.set("q", filters.q.trim());
  if (filters.status?.trim()) params.set("status", filters.status.trim());
  if (filters.view === "archive") params.set("view", "archive");
  if (filters.org_group_id != null) params.set("org_group_id", String(filters.org_group_id));
  if (filters.org_unit_id != null) params.set("org_unit_id", String(filters.org_unit_id));
  if (filters.position_id != null) params.set("position_id", String(filters.position_id));
  if (filters.sort?.trim()) params.set("sort", filters.sort.trim());
  params.set("limit", String(filters.limit ?? 50));
  params.set("offset", String(filters.offset ?? 0));
  return params.toString();
}

export function mapPersonnelApplicationsApiError(error: unknown, fallback: string): string {
  return formatThrownError(error, fallback);
}

export async function listPersonnelApplications(
  filters: PersonnelApplicationListFilters = {},
): Promise<PersonnelApplicationListResponse> {
  const qs = buildQuery(filters);
  const url = qs
    ? `${resolveApiUrl(PERSONNEL_APPLICATIONS_BASE_PATH)}?${qs}`
    : resolveApiUrl(PERSONNEL_APPLICATIONS_BASE_PATH);
  const res = await fetch(url, { method: "GET", headers: authHeaders(), cache: "no-store" });
  const body = await readJsonSafe(res);
  if (!res.ok) throw toApiError(res.status, body, { method: "GET", url: PERSONNEL_APPLICATIONS_BASE_PATH });
  return body as PersonnelApplicationListResponse;
}

export async function previewPersonnelApplication(iin: string): Promise<PersonnelApplicationPreviewResponse> {
  const res = await fetch(resolveApiUrl(`${PERSONNEL_APPLICATIONS_BASE_PATH}/preview`), {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify({ iin }),
    cache: "no-store",
  });
  const body = await readJsonSafe(res);
  if (!res.ok) throw toApiError(res.status, body, { method: "POST", url: `${PERSONNEL_APPLICATIONS_BASE_PATH}/preview` });
  return body as PersonnelApplicationPreviewResponse;
}

export async function registerPersonnelApplication(
  payload: PersonnelApplicationRegisterBody,
): Promise<PersonnelApplicationRegisterResponse> {
  const res = await fetch(resolveApiUrl(PERSONNEL_APPLICATIONS_BASE_PATH), {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify(payload),
    cache: "no-store",
  });
  const body = await readJsonSafe(res);
  if (!res.ok) throw toApiError(res.status, body, { method: "POST", url: PERSONNEL_APPLICATIONS_BASE_PATH });
  return body as PersonnelApplicationRegisterResponse;
}

export async function getPersonnelApplication(applicationId: number): Promise<PersonnelApplicationDetail> {
  const path = `${PERSONNEL_APPLICATIONS_BASE_PATH}/${applicationId}`;
  const res = await fetch(resolveApiUrl(path), { method: "GET", headers: authHeaders(), cache: "no-store" });
  const body = await readJsonSafe(res);
  if (!res.ok) throw toApiError(res.status, body, { method: "GET", url: path });
  return body as PersonnelApplicationDetail;
}

export async function getPersonApplicationsHistory(
  personId: number,
): Promise<PersonnelApplicationHistoryResponse> {
  const path = `/api/ppr/persons/${encodeURIComponent(String(personId))}/applications`;
  const res = await fetch(resolveApiUrl(path), { method: "GET", headers: authHeaders(), cache: "no-store" });
  const body = await readJsonSafe(res);
  if (!res.ok) throw toApiError(res.status, body, { method: "GET", url: path });
  return body as PersonnelApplicationHistoryResponse;
}

export type IntakeLinkIssueResponse = {
  application_id: number;
  link_id: number;
  intake_url_path: string;
  expires_at: string;
  status: string;
  reissued: boolean;
};

export type IntakeSummaryResponse = {
  application_id: number;
  link_status: string | null;
  draft_status: string | null;
  link_id: number | null;
  issued_at: string | null;
  expires_at: string | null;
  opened_at: string | null;
  submitted_at: string | null;
  revoked_at: string | null;
  intake_url_path: string | null;
};

export async function issueIntakeLink(applicationId: number): Promise<IntakeLinkIssueResponse> {
  const path = `${PERSONNEL_APPLICATIONS_BASE_PATH}/${applicationId}/intake-link`;
  const res = await fetch(resolveApiUrl(path), {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify({}),
    cache: "no-store",
  });
  const body = await readJsonSafe(res);
  if (!res.ok) throw toApiError(res.status, body, { method: "POST", url: path });
  return body as IntakeLinkIssueResponse;
}

export async function reissueIntakeLink(applicationId: number): Promise<IntakeLinkIssueResponse> {
  const path = `${PERSONNEL_APPLICATIONS_BASE_PATH}/${applicationId}/intake-link/reissue`;
  const res = await fetch(resolveApiUrl(path), {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify({}),
    cache: "no-store",
  });
  const body = await readJsonSafe(res);
  if (!res.ok) throw toApiError(res.status, body, { method: "POST", url: path });
  return body as IntakeLinkIssueResponse;
}

export async function revokeIntakeLink(applicationId: number): Promise<{ application_id: number; link_id: number; status: string; revoked_at: string }> {
  const path = `${PERSONNEL_APPLICATIONS_BASE_PATH}/${applicationId}/intake-link/revoke`;
  const res = await fetch(resolveApiUrl(path), {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify({}),
    cache: "no-store",
  });
  const body = await readJsonSafe(res);
  if (!res.ok) throw toApiError(res.status, body, { method: "POST", url: path });
  return body as { application_id: number; link_id: number; status: string; revoked_at: string };
}

export async function getIntakeSummary(applicationId: number): Promise<IntakeSummaryResponse> {
  const path = `${PERSONNEL_APPLICATIONS_BASE_PATH}/${applicationId}/intake`;
  const res = await fetch(resolveApiUrl(path), { method: "GET", headers: authHeaders(), cache: "no-store" });
  const body = await readJsonSafe(res);
  if (!res.ok) throw toApiError(res.status, body, { method: "GET", url: path });
  return body as IntakeSummaryResponse;
}

export type IntakeReviewSection = {
  section_code: string;
  section_label: string;
  status: string;
  rework_comment: string | null;
  reviewed_by_user_id: number | null;
  reviewed_at: string | null;
  is_empty: boolean;
  payload: Record<string, unknown> | unknown[];
};

export type IntakeTransferAudit = {
  transfer_id: number;
  application_id: number;
  status: string;
  result: string | null;
  transferred_by_user_id: number | null;
  transferred_at: string | null;
  sections_transferred: string[];
  command_ids: string[];
  error_message: string | null;
};

export type IntakeReviewState = {
  application_id: number;
  draft: {
    application_id: number;
    draft_id: number;
    payload: Record<string, unknown>;
    status: string;
    read_only: boolean;
  };
  sections: IntakeReviewSection[];
  transfer: IntakeTransferAudit | null;
  can_transfer: boolean;
  transfer_blocked_reason: string | null;
};

export async function getIntakeReviewState(applicationId: number): Promise<IntakeReviewState> {
  const path = `${PERSONNEL_APPLICATIONS_BASE_PATH}/${applicationId}/intake/review`;
  const res = await fetch(resolveApiUrl(path), { method: "GET", headers: authHeaders(), cache: "no-store" });
  const body = await readJsonSafe(res);
  if (!res.ok) throw toApiError(res.status, body, { method: "GET", url: path });
  return body as IntakeReviewState;
}

async function postReviewAction(
  applicationId: number,
  sectionCode: string,
  action: "accept" | "skip" | "rework",
  comment?: string,
): Promise<IntakeReviewState> {
  const path =
    action === "rework"
      ? `${PERSONNEL_APPLICATIONS_BASE_PATH}/${applicationId}/intake/review/sections/${encodeURIComponent(sectionCode)}/rework`
      : `${PERSONNEL_APPLICATIONS_BASE_PATH}/${applicationId}/intake/review/sections/${encodeURIComponent(sectionCode)}/${action}`;
  const res = await fetch(resolveApiUrl(path), {
    method: "POST",
    headers: authHeaders(true),
    body: action === "rework" ? JSON.stringify({ comment: comment ?? "" }) : JSON.stringify({}),
    cache: "no-store",
  });
  const body = await readJsonSafe(res);
  if (!res.ok) throw toApiError(res.status, body, { method: "POST", url: path });
  return body as IntakeReviewState;
}

export function acceptIntakeSection(applicationId: number, sectionCode: string) {
  return postReviewAction(applicationId, sectionCode, "accept");
}

export function skipIntakeSection(applicationId: number, sectionCode: string) {
  return postReviewAction(applicationId, sectionCode, "skip");
}

export function reworkIntakeSection(applicationId: number, sectionCode: string, comment: string) {
  return postReviewAction(applicationId, sectionCode, "rework", comment);
}

export async function transferIntakeToPpr(applicationId: number): Promise<{
  application_id: number;
  transfer: IntakeTransferAudit;
  idempotent_replay: boolean;
}> {
  const path = `${PERSONNEL_APPLICATIONS_BASE_PATH}/${applicationId}/intake/transfer`;
  const res = await fetch(resolveApiUrl(path), {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify({}),
    cache: "no-store",
  });
  const body = await readJsonSafe(res);
  if (!res.ok) throw toApiError(res.status, body, { method: "POST", url: path });
  return body as { application_id: number; transfer: IntakeTransferAudit; idempotent_replay: boolean };
}

export type DirectorResolutionAuditItem = {
  audit_id: number;
  application_id: number;
  action: string;
  previous_application_status: string | null;
  new_application_status: string;
  previous_resolution_status: string | null;
  new_resolution_status: string | null;
  comment: string | null;
  actor_user_id: number;
  created_at: string;
};

export async function openDirectorResolution(applicationId: number) {
  const path = `${PERSONNEL_APPLICATIONS_BASE_PATH}/${applicationId}/director-resolution/open`;
  const res = await fetch(resolveApiUrl(path), {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify({}),
    cache: "no-store",
  });
  const body = await readJsonSafe(res);
  if (!res.ok) throw toApiError(res.status, body, { method: "POST", url: path });
  return body;
}

export async function recordDirectorResolution(
  applicationId: number,
  outcome: string,
  comment?: string,
) {
  const path = `${PERSONNEL_APPLICATIONS_BASE_PATH}/${applicationId}/director-resolution`;
  const res = await fetch(resolveApiUrl(path), {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify({ outcome, comment: comment ?? "" }),
    cache: "no-store",
  });
  const body = await readJsonSafe(res);
  if (!res.ok) throw toApiError(res.status, body, { method: "POST", url: path });
  return body;
}

export async function changeDirectorResolution(
  applicationId: number,
  outcome: string,
  comment?: string,
) {
  const path = `${PERSONNEL_APPLICATIONS_BASE_PATH}/${applicationId}/director-resolution/change`;
  const res = await fetch(resolveApiUrl(path), {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify({ outcome, comment: comment ?? "" }),
    cache: "no-store",
  });
  const body = await readJsonSafe(res);
  if (!res.ok) throw toApiError(res.status, body, { method: "POST", url: path });
  return body;
}

export async function reopenDirectorResolution(applicationId: number) {
  const path = `${PERSONNEL_APPLICATIONS_BASE_PATH}/${applicationId}/director-resolution/reopen`;
  const res = await fetch(resolveApiUrl(path), {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify({}),
    cache: "no-store",
  });
  const body = await readJsonSafe(res);
  if (!res.ok) throw toApiError(res.status, body, { method: "POST", url: path });
  return body;
}

export async function getDirectorResolutionAudit(
  applicationId: number,
): Promise<DirectorResolutionAuditItem[]> {
  const path = `${PERSONNEL_APPLICATIONS_BASE_PATH}/${applicationId}/director-resolution/audit`;
  const res = await fetch(resolveApiUrl(path), { method: "GET", headers: authHeaders(), cache: "no-store" });
  const body = await readJsonSafe(res);
  if (!res.ok) throw toApiError(res.status, body, { method: "GET", url: path });
  return (body as { items: DirectorResolutionAuditItem[] }).items;
}

export async function createHireOrderDraft(applicationId: number): Promise<{
  application_id: number;
  personnel_order_id: number;
  idempotent_replay: boolean;
  application_status: string;
}> {
  const path = `${PERSONNEL_APPLICATIONS_BASE_PATH}/${applicationId}/hire-order-draft`;
  const res = await fetch(resolveApiUrl(path), {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify({}),
    cache: "no-store",
  });
  const body = await readJsonSafe(res);
  if (!res.ok) throw toApiError(res.status, body, { method: "POST", url: path });
  return body as {
    application_id: number;
    personnel_order_id: number;
    idempotent_replay: boolean;
    application_status: string;
  };
}

export async function applyPersonnelApplication(applicationId: number): Promise<{
  application_id: number;
  personnel_order_id: number;
  employee_id: number;
  idempotent_replay: boolean;
  application_status: string;
}> {
  const path = `${PERSONNEL_APPLICATIONS_BASE_PATH}/${applicationId}/apply`;
  const res = await fetch(resolveApiUrl(path), {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify({}),
    cache: "no-store",
  });
  const body = await readJsonSafe(res);
  if (!res.ok) throw toApiError(res.status, body, { method: "POST", url: path });
  return body as {
    application_id: number;
    personnel_order_id: number;
    employee_id: number;
    idempotent_replay: boolean;
    application_status: string;
  };
}

export type TimelineEventItem = {
  code: string;
  label: string;
  occurred_at: string;
  actor_user_id?: number | null;
  detail?: string | null;
  metadata?: Record<string, unknown> | null;
};

export type CombinedAuditItem = {
  source: string;
  audit_id: number;
  action: string;
  previous_status: string | null;
  new_status: string | null;
  comment: string | null;
  actor_user_id: number | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
};

export async function cancelPersonnelApplication(
  applicationId: number,
  reason: string,
): Promise<{
  application_id: number;
  status: string;
  closed_at: string;
  audit: CombinedAuditItem;
}> {
  const path = `${PERSONNEL_APPLICATIONS_BASE_PATH}/${applicationId}/cancel`;
  const res = await fetch(resolveApiUrl(path), {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify({ reason }),
    cache: "no-store",
  });
  const body = await readJsonSafe(res);
  if (!res.ok) throw toApiError(res.status, body, { method: "POST", url: path });
  return body as {
    application_id: number;
    status: string;
    closed_at: string;
    audit: CombinedAuditItem;
  };
}

export async function getApplicationTimeline(applicationId: number): Promise<{
  application_id: number;
  items: TimelineEventItem[];
}> {
  const path = `${PERSONNEL_APPLICATIONS_BASE_PATH}/${applicationId}/timeline`;
  const res = await fetch(resolveApiUrl(path), { method: "GET", headers: authHeaders(), cache: "no-store" });
  const body = await readJsonSafe(res);
  if (!res.ok) throw toApiError(res.status, body, { method: "GET", url: path });
  return body as { application_id: number; items: TimelineEventItem[] };
}

export async function getLifecycleAudit(applicationId: number): Promise<{ items: CombinedAuditItem[] }> {
  const path = `${PERSONNEL_APPLICATIONS_BASE_PATH}/${applicationId}/lifecycle-audit`;
  const res = await fetch(resolveApiUrl(path), { method: "GET", headers: authHeaders(), cache: "no-store" });
  const body = await readJsonSafe(res);
  if (!res.ok) throw toApiError(res.status, body, { method: "GET", url: path });
  return body as { items: CombinedAuditItem[] };
}
