/** MRD REST API client (WP-MRD-004). */
import { buildHeaders } from "@/lib/api";
import { formatThrownError } from "@/lib/i18n";
import { resolveApiUrl } from "@/lib/apiBase";

function getDevUserId(): string | null {
  const appEnv = (process.env.NEXT_PUBLIC_APP_ENV || "dev").trim().toLowerCase();
  if (appEnv === "prod" || appEnv === "production") return null;
  const v = (process.env.NEXT_PUBLIC_DEV_X_USER_ID || "").trim();
  return v ? v : null;
}

function buildQuery(params: Record<string, string | number | boolean | null | undefined>): string {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === null) return;
    if (typeof v === "boolean") {
      q.set(k, v ? "true" : "false");
      return;
    }
    const s = String(v).trim();
    if (!s) return;
    q.set(k, s);
  });
  return q.toString();
}

function authHeaders(json = false): Record<string, string> {
  const extra: Record<string, string> = { Accept: "application/json" };
  if (json) extra["Content-Type"] = "application/json";
  const devUserId = getDevUserId();
  if (devUserId) extra["X-User-Id"] = devUserId;
  return buildHeaders(extra) as Record<string, string>;
}

function parseErrorBody(status: number, body: string, fallback: string): Error {
  try {
    const parsed = JSON.parse(body) as { detail?: unknown };
    if (typeof parsed.detail === "string") return new Error(parsed.detail);
    if (parsed.detail && typeof parsed.detail === "object") {
      return new Error(JSON.stringify(parsed.detail));
    }
  } catch {
    // ignore
  }
  if (status === 403) return new Error("Недостаточно прав.");
  if (status === 404) return new Error("Эталон не найден.");
  if (status === 409) return new Error(body || "Операция не может быть выполнена из‑за конфликта данных.");
  if (status === 422) return new Error(body || "Некорректные параметры.");
  return new Error(fallback);
}

async function apiGetJson<T>(path: string, qs?: string): Promise<T> {
  const url = resolveApiUrl(`${path}${qs ? `?${qs}` : ""}`);
  const resp = await fetch(url, { headers: authHeaders(), cache: "no-store" });
  const body = await resp.text();
  if (!resp.ok) throw parseErrorBody(resp.status, body, `HTTP ${resp.status}`);
  return JSON.parse(body) as T;
}

async function apiPostJson<T>(path: string, payload: unknown): Promise<T> {
  const url = resolveApiUrl(path);
  const resp = await fetch(url, {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify(payload),
    cache: "no-store",
  });
  const body = await resp.text();
  if (!resp.ok) throw parseErrorBody(resp.status, body, `HTTP ${resp.status}`);
  return JSON.parse(body) as T;
}

export type MonthlyReferenceSummary = {
  mrd_id: number;
  report_period: string;
  version: number;
  status: string;
  row_version: number;
  entry_count: number;
  forked_from_reference_id: number | null;
  is_active_for_period: boolean;
};

export type ActiveMrdResponse = {
  report_period: string;
  active: MonthlyReferenceSummary | null;
};

export type MonthlyReferenceListResponse = {
  report_period: string | null;
  active: MonthlyReferenceSummary | null;
  items: MonthlyReferenceSummary[];
};

export type ForkSourcesResponse = {
  items: MonthlyReferenceSummary[];
  active_by_period: Record<string, number>;
};

export type ForkMutationResponse = {
  status: "committed" | "idempotent_replay";
  result: {
    command_id: string;
    source_mrd_id: number;
    target_mrd_id: number;
    target_report_period: string;
    target_version: number;
    closed_mrd_id: number | null;
    copied_entry_count: number;
    version_event_ids: number[];
  };
};

export function createMrdCommandId(prefix: string): string {
  const suffix =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${prefix}-${suffix}`;
}

export function getActiveMonthlyReference(reportPeriod: string): Promise<ActiveMrdResponse> {
  return apiGetJson("/directory/personnel/monthly-references/active", buildQuery({ report_period: reportPeriod }));
}

export function listMonthlyReferences(reportPeriod?: string): Promise<MonthlyReferenceListResponse> {
  return apiGetJson(
    "/directory/personnel/monthly-references",
    reportPeriod ? buildQuery({ report_period: reportPeriod }) : undefined,
  );
}

export function listMonthlyReferenceForkSources(): Promise<ForkSourcesResponse> {
  return apiGetJson("/directory/personnel/monthly-references/fork-sources");
}

export function forkMonthlyReferenceVersion(body: {
  command_id: string;
  source_mrd_id: number;
  expected_active_row_version?: number | null;
  notes?: string | null;
}): Promise<ForkMutationResponse> {
  return apiPostJson("/directory/personnel/monthly-references/fork-version", body);
}

export function forkMonthlyReferencePeriod(body: {
  command_id: string;
  source_mrd_id: number;
  target_report_period: string;
  notes?: string | null;
}): Promise<ForkMutationResponse> {
  return apiPostJson("/directory/personnel/monthly-references/fork-period", body);
}

export type MrdCreationWindowResponse = {
  reference_date: string;
  allowed_periods: string[];
};

export type MrdWorkspaceEntry = {
  entry_id: number;
  match_key: string;
  entity_scope: string;
  record_kind: string;
  effective_payload: Record<string, unknown>;
  row_version: number;
};

export type MrdConfirmedChangeRow = {
  confirmed_change_id: number;
  entity_scope: string;
  attribute: string;
  old_value: unknown;
  new_value: unknown;
  confirmed_at: string;
  difference_origin_code: string;
  source_batch_id: number | null;
  basis: string | null;
};

export type MrdWorkspaceResponse = {
  summary: MonthlyReferenceSummary;
  metrics: {
    detected_differences_count: number;
    pending_differences_count: number;
    confirmed_changes_count: number;
  };
  entries: {
    total: number;
    items: MrdWorkspaceEntry[];
  };
  confirmed_changes: {
    total: number;
    items: MrdConfirmedChangeRow[];
  };
};

export function getMrdCreationWindow(): Promise<MrdCreationWindowResponse> {
  return apiGetJson("/directory/personnel/monthly-references/creation-window");
}

export function getMrdWorkspace(
  mrdId: number,
  options?: {
    entries_limit?: number;
    entries_offset?: number;
    confirmed_limit?: number;
    confirmed_offset?: number;
  },
): Promise<MrdWorkspaceResponse> {
  return apiGetJson(
    `/directory/personnel/monthly-references/${mrdId}/workspace`,
    buildQuery({
      entries_limit: options?.entries_limit ?? 50,
      entries_offset: options?.entries_offset ?? 0,
      confirmed_limit: options?.confirmed_limit ?? 20,
      confirmed_offset: options?.confirmed_offset ?? 0,
    }),
  );
}

export type HrReviewDifference = {
  difference_id: number;
  attribute: string;
  field_label: string;
  old_value: unknown;
  new_value: unknown;
  detected_value: unknown;
  source_label: string | null;
  lifecycle_status: string;
  decision_status: string;
  technical_diff_class: string | null;
  record_kind: string | null;
  row_version: number;
  actions_available: boolean;
};

export type HrReviewEmployee = {
  match_key: string;
  employee_id: number | null;
  full_name: string;
  position_raw: string;
  rate: string | null;
  category: string | null;
  difference_count: number;
  review_status: string;
  differences: HrReviewDifference[];
};

export type HrReviewDepartmentSummary = {
  total_employees: number;
  without_changes: number;
  with_changes: number;
  awaiting_decision: number;
  confirmed: number;
  rejected: number;
};

export type HrReviewResponse = {
  summary: MonthlyReferenceSummary;
  org_groups: Array<{ value: string; label: string; group_id?: number | null }>;
  departments: Array<{ org_unit_id: number; org_unit_name: string; org_group_id: number }>;
  department_summary: HrReviewDepartmentSummary | null;
  employees: {
    total: number;
    items: HrReviewEmployee[];
  };
};

export function getMrdHrReview(
  mrdId: number,
  options?: {
    org_group_id?: number | null;
    effective_log_group?: string | null;
    org_unit_id?: number | null;
    changed_only?: boolean;
    search?: string | null;
    review_status?: string | null;
    limit?: number;
    offset?: number;
  },
): Promise<HrReviewResponse> {
  return apiGetJson(
    `/directory/personnel/monthly-references/${mrdId}/hr-review`,
    buildQuery({
      org_group_id: options?.org_group_id ?? undefined,
      effective_log_group: options?.effective_log_group ?? undefined,
      org_unit_id: options?.org_unit_id ?? undefined,
      changed_only: options?.changed_only ?? true,
      search: options?.search ?? undefined,
      review_status: options?.review_status ?? undefined,
      limit: options?.limit ?? 50,
      offset: options?.offset ?? 0,
    }),
  );
}

export function mapMrdApiError(error: unknown): string {
  return formatThrownError(error);
}
