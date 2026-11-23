import { apiFetchJson } from "@/lib/api";

const base = "/directory/electronic-hire";

export type FormerCandidate = { person_id: number; full_name: string; iin: string };
export type ElectronicHireCreate = {
  iin: string; full_name: string; birth_date?: string; application_received_at: string; planned_start_date: string;
  org_unit_id: number; position_id: number; employment_rate: number; org_group_id?: number | null;
  idempotency_key?: string;
};

export function searchFormerCandidates(q: string) {
  return apiFetchJson<{ items: FormerCandidate[] }>(`${base}/former-candidates?q=${encodeURIComponent(q)}`);
}

export function createElectronicHire(payload: ElectronicHireCreate) {
  return apiFetchJson<{ application_id: number; person_id: number; card_href: string; action: string }>(`${base}/applications`, {
    method: "POST", body: payload,
  });
}

export function printElectronicHire(applicationId: number) {
  return apiFetchJson<{ ru: string; kk: string }>(`${base}/applications/${applicationId}/print`);
}

export function checkElectronicHire(applicationId: number) {
  return apiFetchJson<{ candidate_checked: boolean }>(`${base}/applications/${applicationId}/candidate-checked`, { method: "POST" });
}

export function getElectronicHire(applicationId: number) {
  return apiFetchJson<Record<string, unknown>>(`${base}/applications/${applicationId}`);
}

export function listElectronicHireApplications() {
  return apiFetchJson<{items: Array<{application_id: number; person_id: number; full_name: string;
    status: string; planned_start_date: string; personnel_order_id: number | null}>}>(`${base}/applications`);
}

export function createElectronicHireOrderDraft(applicationId: number) {
  return apiFetchJson<{personnel_order_id: number; idempotent_replay: boolean; notification: {status: string; last_error?: string | null}}>(`${base}/applications/${applicationId}/order-draft`, {method: "POST"});
}

export function updateElectronicHireConditions(applicationId: number, payload: {org_unit_id: number; position_id: number;
  employment_rate: number; planned_start_date: string}) {
  return apiFetchJson(`${base}/applications/${applicationId}/conditions`, {method: "PATCH", body: payload});
}

export function retryElectronicHireNotification(applicationId: number) {
  return apiFetchJson<{status: string; last_error?: string | null}>(`${base}/applications/${applicationId}/notification/retry`, {method: "POST"});
}

export function sendElectronicHireLinkTelegram(applicationId: number) {
  return apiFetchJson<{status: string; last_error?: string | null}>(`${base}/applications/${applicationId}/intake-link/telegram`, {method: "POST"});
}

export type HireApprovalItem = { application_id: number; full_name: string; org_unit: string;
  position: string; employment_rate: number | string; planned_start_date: string;
  current_visa: {decision: string; is_current: boolean; explanation?: string | null} | null };

export function listHireApprovals() {
  return apiFetchJson<{items: HireApprovalItem[]}>(`${base}/approvals`);
}

export function recordHireVisa(applicationId: number, decision: "approved" | "rejected", explanation?: string) {
  return apiFetchJson(`${base}/applications/${applicationId}/visa`, {method: "POST", body: {decision, explanation}});
}

export function getHireApplicationForOrder(orderId: number) {
  return apiFetchJson<{application_id: number; full_name: string; current_visa: {decision: string; is_current: boolean} | null;
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
