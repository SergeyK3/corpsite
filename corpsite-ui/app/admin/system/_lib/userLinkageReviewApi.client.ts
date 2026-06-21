// FILE: corpsite-ui/app/admin/system/_lib/userLinkageReviewApi.client.ts
import { apiFetchJson } from "@/lib/api";
import { formatThrownError } from "@/lib/i18n";

export type UserLinkageReviewCandidate = {
  user_id: number;
  login?: string | null;
  user_full_name?: string | null;
  proposed_employee_id?: number | null;
  employee_name?: string | null;
  match_strategy?: string | null;
  classification: string;
  confidence?: string | null;
  reason_codes: string[];
  blockers: string[];
  requires_manual_confirmation: boolean;
  decision_state: string;
  latest_decision_id?: number | null;
  latest_decision_at?: string | null;
  reviewer_user_id?: number | null;
  reviewer_login?: string | null;
  decision_reason?: string | null;
};

export type UserLinkageReviewSummary = {
  review_required: number;
  ambiguous: number;
  approved: number;
  rejected: number;
  deferred: number;
  pending: number;
};

export type UserLinkageReviewQueueResponse = {
  phase: string;
  generated_at: string;
  summary: UserLinkageReviewSummary;
  candidates: UserLinkageReviewCandidate[];
  total: number;
  limit: number;
  offset: number;
};

export type UserLinkageReviewDecision = {
  decision_id: number;
  reviewer_user_id: number;
  user_id: number;
  proposed_employee_id?: number | null;
  classification: string;
  match_strategy?: string | null;
  decision: string;
  reason?: string | null;
  created_at?: string | null;
};

export type UserLinkageReviewAuditItem = {
  decision_id: number;
  reviewer_user_id: number;
  reviewer_login?: string | null;
  user_id: number;
  user_login?: string | null;
  user_full_name?: string | null;
  proposed_employee_id?: number | null;
  employee_name?: string | null;
  classification: string;
  match_strategy?: string | null;
  decision: string;
  reason?: string | null;
  created_at?: string | null;
};

export type UserLinkageReviewAuditResponse = {
  items: UserLinkageReviewAuditItem[];
  total: number;
  limit: number;
  offset: number;
};

export type UserLinkageReviewFilters = {
  classification?: string;
  strategy?: string;
  decision_state?: string;
  search?: string;
  limit?: number;
  offset?: number;
};

function buildQuery(params: Record<string, string | number | undefined>): string {
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === "") continue;
    searchParams.set(key, String(value));
  }
  const query = searchParams.toString();
  return query ? `?${query}` : "";
}

export async function fetchUserLinkageReviewQueue(
  filters: UserLinkageReviewFilters = {},
): Promise<UserLinkageReviewQueueResponse> {
  const query = buildQuery({
    classification: filters.classification,
    strategy: filters.strategy,
    decision_state: filters.decision_state,
    search: filters.search,
    limit: filters.limit,
    offset: filters.offset,
  });
  return apiFetchJson<UserLinkageReviewQueueResponse>(
    `/admin/personnel/identity/user-linkage/review${query}`,
  );
}

export async function fetchUserLinkageReviewAudit(params: {
  user_id?: number;
  limit?: number;
  offset?: number;
} = {}): Promise<UserLinkageReviewAuditResponse> {
  const query = buildQuery({
    user_id: params.user_id,
    limit: params.limit,
    offset: params.offset,
  });
  return apiFetchJson<UserLinkageReviewAuditResponse>(
    `/admin/personnel/identity/user-linkage/review/audit${query}`,
  );
}

export async function approveUserLinkageReview(
  userId: number,
  reason?: string,
): Promise<UserLinkageReviewDecision> {
  return apiFetchJson<UserLinkageReviewDecision>(
    `/admin/personnel/identity/user-linkage/review/${userId}/approve`,
    { method: "POST", body: { reason: reason ?? null } },
  );
}

export async function rejectUserLinkageReview(
  userId: number,
  reason?: string,
): Promise<UserLinkageReviewDecision> {
  return apiFetchJson<UserLinkageReviewDecision>(
    `/admin/personnel/identity/user-linkage/review/${userId}/reject`,
    { method: "POST", body: { reason: reason ?? null } },
  );
}

export async function deferUserLinkageReview(
  userId: number,
  reason?: string,
): Promise<UserLinkageReviewDecision> {
  return apiFetchJson<UserLinkageReviewDecision>(
    `/admin/personnel/identity/user-linkage/review/${userId}/defer`,
    { method: "POST", body: { reason: reason ?? null } },
  );
}

export function mapUserLinkageReviewApiError(err: unknown, fallback: string): string {
  return formatThrownError(err, fallback);
}
