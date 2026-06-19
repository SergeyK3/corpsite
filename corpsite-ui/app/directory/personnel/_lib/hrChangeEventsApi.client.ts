import { buildHeaders } from "@/lib/api";
import { formatThrownError } from "@/lib/i18n";
import { resolveApiUrl } from "@/lib/apiBase";

import type { HrChangeEventType } from "./hrChangeEventLabels";

export type { HrChangeEventType } from "./hrChangeEventLabels";
export {
  HR_CHANGE_EVENT_FILTER_OPTIONS,
  HR_CHANGE_EVENT_TYPE_LABELS,
  HR_CHANGE_EVENT_TYPES,
  formatHrChangeEventDate,
  formatHrChangeEventValue,
  hrChangeEventBadgeClass,
  hrChangeEventFieldLabel,
  hrChangeEventTypeLabel,
  isHrChangeEventType,
} from "./hrChangeEventLabels";

export type HrChangeEventRow = {
  change_event_id: number;
  prior_snapshot_id: number;
  new_snapshot_id: number;
  event_type: HrChangeEventType | string;
  event_at: string;
  employee_id: number | null;
  match_key: string;
  record_kind: string;
  prior_entry_id: number | null;
  new_entry_id: number | null;
  field_name: string | null;
  old_value: string | null;
  new_value: string | null;
  department: string | null;
  org_unit_id: number | null;
  full_name: string | null;
  iin: string | null;
  details: Record<string, unknown> | null;
};

export type HrChangeEventsListResponse = {
  items: HrChangeEventRow[];
  total: number;
  limit: number;
  offset: number;
};

export type HrChangeEventsFilters = {
  employee_id?: number;
  department?: string;
  org_unit_id?: number;
  event_type?: HrChangeEventType | string;
  date_from?: string;
  date_to?: string;
  prior_snapshot_id?: number;
  new_snapshot_id?: number;
  source_batch_id?: number;
  q?: string;
  limit?: number;
  offset?: number;
};

export const HR_CHANGE_EVENTS_BASE_PATH = "/directory/personnel/hr-change-events";

function getDevUserId(): string | null {
  const appEnv = (process.env.NEXT_PUBLIC_APP_ENV || "dev").trim().toLowerCase();
  if (appEnv === "prod" || appEnv === "production") return null;
  const v = (process.env.NEXT_PUBLIC_DEV_X_USER_ID || "").trim();
  return v ? v : null;
}

function authHeaders(): Record<string, string> {
  const extra: Record<string, string> = { Accept: "application/json" };
  const devUserId = getDevUserId();
  if (devUserId) extra["X-User-Id"] = devUserId;
  return buildHeaders(extra) as Record<string, string>;
}

function parseErrorBody(status: number, body: string, fallback: string): Error {
  if (status === 403) {
    return new Error("Недостаточно прав для просмотра изменений реестра.");
  }
  const trimmed = body.trim();
  if (trimmed.startsWith("{")) {
    try {
      const parsed = JSON.parse(trimmed) as { detail?: unknown };
      if (typeof parsed.detail === "string" && parsed.detail.trim()) {
        return new Error(parsed.detail.trim());
      }
    } catch {
      // keep raw body fallback
    }
  }
  return new Error(trimmed || fallback || `HTTP ${status}`);
}

export function mapHrChangeEventsApiError(e: unknown, fallback = "Ошибка запроса."): string {
  return formatThrownError(e, { fallback });
}

export function buildHrChangeEventsQueryParams(
  filters: HrChangeEventsFilters,
  options?: { includeClientSearch?: boolean },
): URLSearchParams {
  const params = new URLSearchParams();
  const includeClientSearch = options?.includeClientSearch ?? true;

  if (filters.employee_id != null && filters.employee_id > 0) {
    params.set("employee_id", String(filters.employee_id));
  }
  if (filters.department?.trim()) params.set("department", filters.department.trim());
  if (filters.org_unit_id != null && filters.org_unit_id > 0) {
    params.set("org_unit_id", String(filters.org_unit_id));
  }
  if (filters.event_type?.trim()) params.set("event_type", filters.event_type.trim());
  if (filters.date_from?.trim()) params.set("date_from", filters.date_from.trim());
  if (filters.date_to?.trim()) params.set("date_to", filters.date_to.trim());
  if (filters.prior_snapshot_id != null && filters.prior_snapshot_id > 0) {
    params.set("prior_snapshot_id", String(filters.prior_snapshot_id));
  }
  if (filters.new_snapshot_id != null && filters.new_snapshot_id > 0) {
    params.set("new_snapshot_id", String(filters.new_snapshot_id));
  }
  if (filters.source_batch_id != null && filters.source_batch_id > 0) {
    params.set("source_batch_id", String(filters.source_batch_id));
  }
  if (includeClientSearch && filters.q?.trim()) params.set("q", filters.q.trim());
  if (filters.limit != null && filters.limit > 0) params.set("limit", String(filters.limit));
  if (filters.offset != null && filters.offset >= 0) params.set("offset", String(filters.offset));

  return params;
}

export function parseHrChangeEventsFilters(searchParams: URLSearchParams): HrChangeEventsFilters {
  const employeeId = Number(searchParams.get("employee_id"));
  const orgUnitId = Number(searchParams.get("org_unit_id"));
  const priorSnapshotId = Number(searchParams.get("prior_snapshot_id"));
  const newSnapshotId = Number(searchParams.get("new_snapshot_id"));
  const sourceBatchId = Number(searchParams.get("source_batch_id"));

  return {
    employee_id: Number.isFinite(employeeId) && employeeId > 0 ? employeeId : undefined,
    department: searchParams.get("department") || undefined,
    org_unit_id: Number.isFinite(orgUnitId) && orgUnitId > 0 ? orgUnitId : undefined,
    event_type: searchParams.get("event_type") || undefined,
    date_from: searchParams.get("date_from") || undefined,
    date_to: searchParams.get("date_to") || undefined,
    prior_snapshot_id:
      Number.isFinite(priorSnapshotId) && priorSnapshotId > 0 ? priorSnapshotId : undefined,
    new_snapshot_id: Number.isFinite(newSnapshotId) && newSnapshotId > 0 ? newSnapshotId : undefined,
    source_batch_id: Number.isFinite(sourceBatchId) && sourceBatchId > 0 ? sourceBatchId : undefined,
    q: searchParams.get("q") || undefined,
  };
}

export function buildHrChangeEventsHref(filters: HrChangeEventsFilters = {}): string {
  const qs = buildHrChangeEventsQueryParams(filters).toString();
  return qs ? `${HR_CHANGE_EVENTS_BASE_PATH}?${qs}` : HR_CHANGE_EVENTS_BASE_PATH;
}

export function filterHrChangeEventsBySearch(
  items: HrChangeEventRow[],
  query: string | undefined,
): HrChangeEventRow[] {
  const q = String(query || "")
    .trim()
    .toLowerCase();
  if (!q) return items;
  return items.filter((row) => {
    const name = String(row.full_name || "").toLowerCase();
    const iin = String(row.iin || "").toLowerCase();
    const employeeId = row.employee_id != null ? String(row.employee_id) : "";
    return name.includes(q) || iin.includes(q) || employeeId.includes(q);
  });
}

export async function listHrChangeEvents(
  filters: HrChangeEventsFilters = {},
): Promise<HrChangeEventsListResponse> {
  const qs = buildHrChangeEventsQueryParams(filters, { includeClientSearch: false }).toString();
  const url = resolveApiUrl(`/directory/personnel/hr-change-events${qs ? `?${qs}` : ""}`);
  const res = await fetch(url, { method: "GET", headers: authHeaders(), cache: "no-store" });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw parseErrorBody(res.status, body, "Не удалось загрузить изменения реестра.");
  }
  return res.json() as Promise<HrChangeEventsListResponse>;
}
