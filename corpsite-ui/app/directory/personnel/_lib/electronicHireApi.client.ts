import { apiFetchJson } from "@/lib/api";

const base = "/directory/electronic-hire";

export type CandidateNameParts = { last_name: string; first_name: string; middle_name: string };
export type FormerCandidate = { person_id: number; full_name: string; iin: string;
  last_name: string | null; first_name: string | null; middle_name: string | null };
export type ElectronicHireCreate = {
  iin?: string; last_name: string; first_name: string; middle_name?: string;
  birth_date?: string; application_received_at: string; planned_start_date: string;
  org_unit_id: number; position_id?: number; manual_position_name?: string; manual_position_document_ru?: string; employment_rate: number; org_group_id?: number | null;
  idempotency_key?: string;
};

export function searchFormerCandidates(q: string) {
  return apiFetchJson<{ items: FormerCandidate[] }>(`${base}/former-candidates?q=${encodeURIComponent(q)}`);
}

export function createElectronicHire(payload: ElectronicHireCreate) {
  return apiFetchJson<{ application_id: number; person_id: number | null; position_id: number | null;
    manual_position_name: string | null; position_resolution: "catalog" | "unmatched_manual" | "matched_manual";
    card_href: string | null; action: string; approval_mode: "paper" | "electronic" }>(`${base}/applications`, {
    method: "POST", body: payload,
  });
}

export function printElectronicHire(applicationId: number, locale?: "ru" | "kk", preliminary = false) {
  return apiFetchJson<Partial<Record<"ru" | "kk", string>>>(`${base}/applications/${applicationId}/print`,
    { query: { ...(locale ? { locale } : {}), ...(preliminary ? { preliminary: "true" } : {}) } });
}

export function checkElectronicHire(applicationId: number) {
  return apiFetchJson<{ candidate_checked: boolean }>(`${base}/applications/${applicationId}/candidate-checked`, { method: "POST" });
}

export function getElectronicHire(applicationId: number) {
  return apiFetchJson<Record<string, unknown>>(`${base}/applications/${applicationId}`);
}

export function getHireUnitApprovalMode(unitId: number) {
  return apiFetchJson<{approval_mode: "paper" | "electronic"}>(`${base}/units/${unitId}/approval-mode`);
}

export function recordHirePaperConfirmation(applicationId: number, body: {approver_name: string;
  approved_on: string; note?: string; attachment_id?: number | null}) {
  return apiFetchJson(`${base}/applications/${applicationId}/paper-confirmation`, {method: "POST", body});
}

export function updateElectronicHirePreliminaryName(applicationId: number, name: CandidateNameParts) {
  return apiFetchJson<Record<string, unknown>>(`${base}/applications/${applicationId}/preliminary-name`,
    {method: "PATCH", body: name});
}

export function listElectronicHireApplications() {
  return apiFetchJson<{items: Array<{application_id: number; person_id: number | null; full_name: string;
    status: string; planned_start_date: string; personnel_order_id: number | null}>}>(`${base}/applications`);
}

export type ElectronicHireIdentity = {
  preliminary_full_name: string | null; preliminary_iin: string | null;
  applicant_full_name?: string; verified_full_name?: string;
  legacy_full_name?: string | null;
  preliminary_name_parts: CandidateNameParts;
  applicant_name_parts?: CandidateNameParts;
  verified_name_parts?: CandidateNameParts;
  name_differences?: Array<keyof CandidateNameParts>;
  iin?: string; birth_date?: string; person_id: number | null;
  existing_person_id?: number; existing_full_name?: string;
  confirmed: boolean; status: "new" | "former" | "blocked" | "confirmed";
  reason?: string;
};

export function getElectronicHireIdentity(applicationId: number) {
  return apiFetchJson<ElectronicHireIdentity>(`${base}/applications/${applicationId}/identity`);
}

export function confirmElectronicHireIdentity(applicationId: number, applicantName: CandidateNameParts, confirmReuse: boolean) {
  return apiFetchJson<{person_id: number; idempotent_replay: boolean}>(
    `${base}/applications/${applicationId}/identity/confirm`,
    {method: "POST", body: {verified_last_name: applicantName.last_name,
      verified_first_name: applicantName.first_name, verified_middle_name: applicantName.middle_name,
      confirm_reuse: confirmReuse, document_checked: true}},
  );
}

export function createElectronicHireOrderDraft(applicationId: number) {
  return apiFetchJson<{personnel_order_id: number; idempotent_replay: boolean; notification: {status: string; last_error?: string | null}}>(`${base}/applications/${applicationId}/order-draft`, {method: "POST"});
}

export type ElectronicHireOrderPreview = {
  application_id: number; saved: false; template_version_id: number;
  ru: {title: string; preamble: string; body: string; basis: string};
  kk: {title: string; preamble: string; body: string; basis: string};
};

export function getElectronicHireOrderPreview(applicationId: number) {
  return apiFetchJson<ElectronicHireOrderPreview>(`${base}/applications/${applicationId}/order-preview`);
}

export type ElectronicHireOrderReadiness = {
  application_id: number; ready: boolean; identity_confirmed: boolean;
  intake_transferred: boolean; missing_card_fields: string[]; missing_steps: string[];
};

export function getElectronicHireOrderReadiness(applicationId: number) {
  return apiFetchJson<ElectronicHireOrderReadiness>(`${base}/applications/${applicationId}/order-draft-readiness`);
}

export function updateElectronicHireConditions(applicationId: number, payload: {org_unit_id: number; position_id?: number; manual_position_name?: string; manual_position_document_ru?: string;
  employment_rate: number; planned_start_date: string; mode_change_reason?: string}) {
  return apiFetchJson<{ intended_position_id: number | null; manual_position_name: string | null;
    manual_position_document_ru: string | null; position_resolution: "catalog" | "unmatched_manual" | "matched_manual"; approval_mode: "paper" | "electronic" }>(
    `${base}/applications/${applicationId}/conditions`, {method: "PATCH", body: payload});
}

export type PositionReview = {
  request_id: number; application_id: number; personnel_order_id: number | null;
  source_title: string; org_unit_id: number; org_unit_name: string;
  requester_name: string; requested_at: string; explanation: string;
  status: "open" | "resolved"; decision_mode: "existing" | "link" | "new" | null;
  resolved_position_id: number | null; resolved_position_name: string | null;
  resolved_position_name_kk: string | null; decision_note: string | null;
  decider_name: string | null; decided_at: string | null;
};

export type PositionReviewAudit = { audit_id: number; action: string; actor_user_id: number;
  recorded_at: string; details: Record<string, unknown> };

export function requestPositionReview(applicationId: number, explanation: string) {
  return apiFetchJson<PositionReview>(`${base}/applications/${applicationId}/position-request`,
    {method: "POST", body: {explanation}});
}

export function getPositionReview(applicationId: number) {
  return apiFetchJson<{request: PositionReview | null; history: PositionReviewAudit[]}>(
    `${base}/applications/${applicationId}/position-request`);
}

export function listPositionReviews(status?: "open" | "resolved") {
  return apiFetchJson<{items: PositionReview[]}>(`${base}/position-requests${status ? `?status=${status}` : ""}`);
}

export function resolvePositionReview(requestId: number, body: {
  mode: "existing" | "link" | "new"; position_id?: number; new_position?: Record<string, unknown>;
  decision_note?: string;
}) {
  return apiFetchJson<PositionReview & {changes: Record<string, unknown>; reapproval_required: boolean}>(
    `${base}/position-requests/${requestId}/resolve`, {method: "POST", body});
}

export function retryElectronicHireNotification(applicationId: number) {
  return apiFetchJson<{status: string; last_error?: string | null}>(`${base}/applications/${applicationId}/notification/retry`, {method: "POST"});
}

export function sendElectronicHireLinkTelegram(applicationId: number) {
  return apiFetchJson<{status: string; last_error?: string | null}>(`${base}/applications/${applicationId}/intake-link/telegram`, {method: "POST"});
}

export type HireVisa = {visa_id?: number; decision: string; is_current: boolean; explanation?: string | null;
  decided_by_user_id: number; decided_by_name: string | null; decided_at: string;
  kind?: "paper"; recorded_by_name?: string; approved_on?: string; attachment_id?: number | null};

export type HireApprovalItem = { application_id: number; application_type: string; application_type_label: string;
  approval_mode?: "paper" | "electronic"; full_name: string; org_unit: string;
  position: string; employment_rate: number | string; planned_start_date: string;
  current_visa: HireVisa | null; visa_history?: HireVisa[];
  paper_history?: Array<{confirmation_id: number; approver_name: string; approved_on: string; note?: string; attachment_id?: number | null;
    recorded_by_name: string; recorded_at: string; is_current: boolean}> };

export function listHireApprovals(applicationId?: number) {
  const target = applicationId && applicationId > 0 ? `?application_id=${applicationId}` : "";
  return apiFetchJson<{items: HireApprovalItem[]}>(`${base}/approvals${target}`);
}

export function getHireApprovalStatement(applicationId: number) {
  return apiFetchJson<{ru: string; kk: string}>(`${base}/approvals/${applicationId}/statement`);
}

export function recordHireVisa(applicationId: number, decision: "approved" | "rejected", explanation?: string) {
  return apiFetchJson(`${base}/applications/${applicationId}/visa`, {method: "POST", body: {decision, explanation}});
}

export function getHireApplicationForOrder(orderId: number) {
  return apiFetchJson<{application_id: number; full_name: string; current_visa: {decision: string; is_current: boolean} | null;
    position_resolution: "catalog" | "unmatched_manual" | "matched_manual";
    manual_position_name: string | null; position_request: PositionReview | null;
    visas: Array<{visa_id: number; decision: string; explanation?: string | null; decided_at: string;
      decided_by_user_id: number; is_current: boolean}>}>(`${base}/orders/${orderId}/application`);
}

export async function uploadElectronicHireSignedCopy(applicationId: number, file: File) {
  const { buildHeaders, readJsonSafe, toApiError } = await import("@/lib/api");
  const { resolveApiUrl } = await import("@/lib/apiBase");
  const form = new FormData(); form.append("file", file);
  const path = `${base}/applications/${applicationId}/signed-copy`;
  const response = await fetch(resolveApiUrl(path), { method: "POST", headers: buildHeaders(), body: form });
  const body = await readJsonSafe(response);
  if (!response.ok) throw toApiError(response.status, body);
  return body as { attachment_id: number; file_name: string };
}
