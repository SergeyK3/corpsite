// FILE: corpsite-ui/app/admin/system/_lib/userLinkageOperationsApi.client.ts
import { apiFetchJson } from "@/lib/api";
import { formatThrownError } from "@/lib/i18n";

const BASE = "/admin/personnel/identity/user-linkage/operations";

export type UserLinkageOperationsAuditSummary = {
  user_employee_linked: number;
  user_employee_unlinked: number;
  user_employee_link_rolled_back: number;
};

export type UserLinkageOperationsRunListItem = {
  run_id: number;
  phase: string;
  operation: string;
  status: string;
  dry_run: boolean;
  actor_user_id?: number | null;
  actor_login?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  summary: Record<string, unknown>;
  source_preview_run_id?: number | null;
  source_item_id?: number | null;
  item_count: number;
  audit_summary: UserLinkageOperationsAuditSummary;
};

export type UserLinkageOperationsRunDetail = UserLinkageOperationsRunListItem & {
  item_counts_by_status: Record<string, number>;
  item_counts_by_action: Record<string, number>;
  recent_items: UserLinkageOperationsItemListItem[];
};

export type UserLinkageOperationsItemListItem = {
  item_id: number;
  run_id: number;
  run_operation?: string | null;
  run_status?: string | null;
  user_id: number;
  login?: string | null;
  proposed_employee_id?: number | null;
  employee_name?: string | null;
  action: string;
  status: string;
  reason_codes: string[];
  created_at?: string | null;
  source_item_id?: number | null;
  audit_summary: UserLinkageOperationsAuditSummary;
};

export type UserLinkageOperationsItemDetail = UserLinkageOperationsItemListItem & {
  source_decision_id?: number | null;
  before_user_snapshot: Record<string, unknown>;
  after_user_snapshot: Record<string, unknown>;
  rollback_payload: Record<string, unknown>;
  preview_snapshot: Record<string, unknown>;
  decision_snapshot: Record<string, unknown>;
  run_summary: Record<string, unknown>;
};

export type UserLinkageOperationsRunListResponse = {
  items: UserLinkageOperationsRunListItem[];
  total: number;
  limit: number;
  offset: number;
};

export type UserLinkageOperationsItemListResponse = {
  items: UserLinkageOperationsItemListItem[];
  total: number;
  limit: number;
  offset: number;
};

export type UserLinkageOperationsRunsFilters = {
  operation?: string;
  status?: string;
  actor_user_id?: number;
  created_from?: string;
  created_to?: string;
  limit?: number;
  offset?: number;
};

export type UserLinkageOperationsItemsFilters = {
  run_id?: number;
  action?: string;
  status?: string;
  user_id?: number;
  employee_id?: number;
  limit?: number;
  offset?: number;
};

export type UserLinkageRepairPreviewRequest = {
  user_id?: number;
  employee_id?: number;
  reason: string;
};

export type UserLinkageRepairPreviewResponse = {
  phase: string;
  operation: string;
  run_id: number;
  item_id: number;
  dry_run: boolean;
  target: Record<string, unknown>;
  current_user: Record<string, unknown>;
  current_employee?: Record<string, unknown> | null;
  current_linkage: Record<string, unknown>;
  candidate_linkage?: Record<string, unknown> | null;
  diagnosis_code: string;
  recommended_action: string;
  execute_ready: boolean;
  execute_action: string;
  preview: Record<string, unknown>;
  review: Record<string, unknown>;
  generated_at: string;
};

export type UserLinkageRerunExecuteRequest = {
  source_preview_run_id: number;
  confirm_token: string;
  reason: string;
};

export type UserLinkageRerunExecuteResponse = {
  phase: string;
  operation: string;
  rerun_run_id: number;
  source_preview_run_id: number;
  execute_run_id: number;
  run_status: string;
  items: {
    item_id: number;
    user_id: number;
    action: string;
    status: string;
    applied: boolean;
  }[];
  execute: {
    phase: string;
    dry_run: boolean;
    generated_at: string;
    preview_run_id: number;
    run_id: number;
    run_status: string;
    operation: string;
    applied: number;
    skipped: number;
    failed: number;
    audit_records_created: number;
    items: {
      item_id: number;
      user_id: number;
      action: string;
      status: string;
      applied: boolean;
      audit_created: boolean;
    }[];
  };
  generated_at: string;
};

function buildQuery(params: Record<string, string | number | undefined>): Record<string, string | number> {
  const out: Record<string, string | number> = {};
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === "") continue;
    out[key] = value;
  }
  return out;
}

export async function fetchOperationsRuns(
  filters: UserLinkageOperationsRunsFilters = {},
): Promise<UserLinkageOperationsRunListResponse> {
  return apiFetchJson<UserLinkageOperationsRunListResponse>(`${BASE}/runs`, {
    query: buildQuery({
      operation: filters.operation,
      status: filters.status,
      actor_user_id: filters.actor_user_id,
      created_from: filters.created_from,
      created_to: filters.created_to,
      limit: filters.limit,
      offset: filters.offset,
    }),
  });
}

export async function fetchOperationsRun(runId: number): Promise<UserLinkageOperationsRunDetail> {
  return apiFetchJson<UserLinkageOperationsRunDetail>(`${BASE}/runs/${runId}`);
}

export async function fetchOperationsItems(
  filters: UserLinkageOperationsItemsFilters = {},
): Promise<UserLinkageOperationsItemListResponse> {
  return apiFetchJson<UserLinkageOperationsItemListResponse>(`${BASE}/items`, {
    query: buildQuery({
      run_id: filters.run_id,
      action: filters.action,
      status: filters.status,
      user_id: filters.user_id,
      employee_id: filters.employee_id,
      limit: filters.limit,
      offset: filters.offset,
    }),
  });
}

export async function fetchOperationsItem(itemId: number): Promise<UserLinkageOperationsItemDetail> {
  return apiFetchJson<UserLinkageOperationsItemDetail>(`${BASE}/items/${itemId}`);
}

export async function postRepairPreview(
  body: UserLinkageRepairPreviewRequest,
): Promise<UserLinkageRepairPreviewResponse> {
  return apiFetchJson<UserLinkageRepairPreviewResponse>(`${BASE}/repair-preview`, {
    method: "POST",
    body,
  });
}

export async function postRerunExecute(
  body: UserLinkageRerunExecuteRequest,
): Promise<UserLinkageRerunExecuteResponse> {
  return apiFetchJson<UserLinkageRerunExecuteResponse>(`${BASE}/rerun-execute`, {
    method: "POST",
    body,
  });
}

export function mapUserLinkageOperationsApiError(err: unknown, fallback: string): string {
  return formatThrownError(err, { fallback });
}
