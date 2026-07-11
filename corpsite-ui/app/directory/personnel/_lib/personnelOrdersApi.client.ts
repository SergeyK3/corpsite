import { buildHeaders } from "@/lib/api";
import { formatThrownError } from "@/lib/i18n";
import { resolveApiUrl } from "@/lib/apiBase";
import { readTaskOrgFiltersFromSearchParams } from "@/lib/taskOrgFilters";

import type { PersonnelOrderStatus, PersonnelOrderType } from "./personnelOrderLabels";

export type { PersonnelOrderStatus, PersonnelOrderType } from "./personnelOrderLabels";
export {
  PERSONNEL_ORDER_STATUS_FILTER_OPTIONS,
  PERSONNEL_ORDER_TYPE_FILTER_OPTIONS,
  PERSONNEL_ORDER_CREATE_TYPE_OPTIONS,
  PERSONNEL_ORDER_CREATE_TYPES,
  canApplyPersonnelOrder,
  canApplyPersonnelOrderAction,
  canRegisterPersonnelOrder,
  canVoidPersonnelOrder,
  formatPersonnelOrderDate,
  formatPersonnelOrderDateTime,
  formatPersonnelOrderNumber,
  isEditablePersonnelOrderStatus,
  isPersonnelOrderApplied,
  PERSONNEL_ORDER_APPLIED_LABEL,
  personnelOrderAppliedBadgeClass,
  personnelOrderSourceModeLabel,
  personnelOrderStatusBadgeClass,
  personnelOrderStatusLabel,
  personnelOrderTypeBadgeClass,
  personnelOrderTypeLabel,
} from "./personnelOrderLabels";

export type PersonnelOrderListItem = {
  order_id: number;
  order_number?: string | null;
  order_date?: string | null;
  order_type_code: string;
  order_class: string;
  status: string;
  source_mode: string;
  legal_basis_article?: string | null;
  signed_by_employee_id?: number | null;
  signed_by_name?: string | null;
  signed_by_position?: string | null;
  executor_name?: string | null;
  basis_summary?: string | null;
  comment?: string | null;
  void_reason?: string | null;
  voided_at?: string | null;
  voided_by?: number | null;
  created_by: number;
  created_at?: string | null;
  updated_at?: string | null;
  item_count: number;
  employee_ids: number[];
  employee_names: string[];
};

export type PersonnelOrderItem = {
  item_id: number;
  order_id: number;
  item_number: number;
  item_type_code: string;
  item_status: string;
  employee_id?: number | null;
  employee_name?: string | null;
  org_unit_id?: number | null;
  org_unit_name?: string | null;
  effective_date?: string | null;
  period_start?: string | null;
  period_end?: string | null;
  payload: Record<string, unknown>;
  void_reason?: string | null;
  voided_at?: string | null;
  voided_by?: number | null;
  created_at?: string | null;
};

export type PersonnelOrderLocalizedText = {
  localized_text_id: number;
  order_id: number;
  locale: string;
  title?: string | null;
  preamble?: string | null;
  body_text?: string | null;
  render_version: number;
  is_authoritative: boolean;
  created_at?: string | null;
  updated_at?: string | null;
};

export type PersonnelOrderAttachment = {
  attachment_id: number;
  order_id: number;
  attachment_kind: string;
  storage_type: string;
  file_path?: string | null;
  file_url?: string | null;
  file_comment?: string | null;
  locale?: string | null;
  created_by: number;
  created_at?: string | null;
};

export type PersonnelOrderPrint = {
  print_id: number;
  order_id: number;
  locale: string;
  format: string;
  file_path?: string | null;
  file_url?: string | null;
  is_signed_copy: boolean;
  render_version: number;
  generated_at?: string | null;
  generated_by?: number | null;
};

export type PersonnelOrderLinkedEvent = {
  event_id: number;
  order_id?: number | null;
  order_item_id?: number | null;
  employee_id: number;
  employee_name?: string | null;
  event_type: string;
  event_class: string;
  event_label: string;
  lifecycle_status: string;
  metadata?: Record<string, unknown> | null;
  effective_date?: string | null;
  from_org_unit_id?: number | null;
  from_org_unit_name?: string | null;
  to_org_unit_id?: number | null;
  to_org_unit_name?: string | null;
  from_position_id?: number | null;
  from_position_name?: string | null;
  to_position_id?: number | null;
  to_position_name?: string | null;
  from_rate?: number | null;
  to_rate?: number | null;
  order_ref?: string | null;
  comment?: string | null;
  created_at?: string | null;
};

export type PersonnelOrderHeader = Omit<
  PersonnelOrderListItem,
  "item_count" | "employee_ids" | "employee_names"
>;

export type PersonnelOrdersListResponse = {
  items: PersonnelOrderListItem[];
  total: number;
  limit: number;
  offset: number;
};

export type PersonnelOrderDetailResponse = {
  order: PersonnelOrderHeader;
  items: PersonnelOrderItem[];
  localized_texts: PersonnelOrderLocalizedText[];
  attachments: PersonnelOrderAttachment[];
  prints: PersonnelOrderPrint[];
  events: PersonnelOrderLinkedEvent[];
};

/** WP-PO-EDIT-002 editorial persistence projection. */
export type PersonnelOrderEditorialReviewStatus =
  | "CURRENT"
  | "STALE"
  | "REVIEW_REQUIRED"
  | "GENERATION_FAILED";

export type PersonnelOrderEditorialBlock = {
  block_id: number;
  scope: "order" | "item" | string;
  order_item_id?: number | null;
  locale: "kk" | "ru" | string;
  block_type: "title" | "preamble" | "closing" | "body" | "basis" | string;
  generated_text?: string | null;
  override_text?: string | null;
  effective_text: string;
  generator_key?: string | null;
  generator_version?: string | null;
  source_fingerprint?: string | null;
  review_status: PersonnelOrderEditorialReviewStatus | string;
  basis_required?: boolean | null;
  editable: boolean;
  revision: number;
  generated_at?: string | null;
  edited_at?: string | null;
  edited_by_user_id?: number | null;
};

export type PersonnelOrderEditorialItemGroup = {
  order_item_id: number;
  item_number: number;
  item_type_code: string;
  basis_required: boolean;
  blocks: PersonnelOrderEditorialBlock[];
};

export type PersonnelOrderEditorialState = {
  order_id: number;
  order_status: string;
  editable: boolean;
  order_blocks: PersonnelOrderEditorialBlock[];
  items: PersonnelOrderEditorialItemGroup[];
};

export type PersonnelOrdersFilters = {
  status?: PersonnelOrderStatus | string;
  order_type_code?: PersonnelOrderType | string;
  date_from?: string;
  date_to?: string;
  employee_id?: number;
  org_unit_id?: number;
  order_id?: number;
  q?: string;
  limit?: number;
  offset?: number;
};

export type PersonnelOrderCreatePayload = {
  order_type_code: string;
  order_number?: string | null;
  order_date?: string | null;
  source_mode?: string;
  legal_basis_article?: string | null;
  signed_by_employee_id?: number | null;
  signed_by_name?: string | null;
  signed_by_position?: string | null;
  executor_name?: string | null;
  basis_summary?: string | null;
  comment?: string | null;
};

export type PersonnelOrderUpdatePayload = {
  order_number?: string;
  order_date?: string;
  order_type_code?: string;
  source_mode?: string;
  legal_basis_article?: string | null;
  signed_by_employee_id?: number | null;
  signed_by_name?: string | null;
  signed_by_position?: string | null;
  executor_name?: string | null;
  basis_summary?: string | null;
  comment?: string | null;
};

export type PersonnelOrderItemCreatePayload = {
  item_type_code: string;
  employee_id?: number | null;
  effective_date?: string | null;
  period_start?: string | null;
  period_end?: string | null;
  payload?: Record<string, unknown>;
  item_number?: number;
};

export type PersonnelOrderItemUpdatePayload = {
  item_type_code?: string;
  employee_id?: number | null;
  effective_date?: string | null;
  period_start?: string | null;
  period_end?: string | null;
  payload?: Record<string, unknown>;
  item_number?: number;
};

export const PERSONNEL_ORDERS_BASE_PATH = "/directory/personnel/orders";

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
    return new Error("Недостаточно прав для работы с кадровыми приказами.");
  }
  const trimmed = body.trim();
  if (trimmed.startsWith("{")) {
    try {
      const parsed = JSON.parse(trimmed) as { detail?: unknown };
      if (typeof parsed.detail === "string" && parsed.detail.trim()) {
        return new Error(parsed.detail.trim());
      }
      if (Array.isArray(parsed.detail)) {
        const parts = parsed.detail
          .map((item) => {
            if (typeof item === "string") return item;
            if (item && typeof item === "object" && "msg" in item) {
              return String((item as { msg?: unknown }).msg || "");
            }
            return "";
          })
          .filter(Boolean);
        if (parts.length) return new Error(parts.join("; "));
      }
    } catch {
      // keep raw body fallback
    }
  }
  return new Error(trimmed || fallback || `HTTP ${status}`);
}

async function requestJson<T>(
  method: string,
  path: string,
  options?: { body?: unknown; fallback?: string },
): Promise<T> {
  const res = await fetch(resolveApiUrl(path), {
    method,
    headers: {
      ...authHeaders(),
      ...(options?.body !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    body: options?.body !== undefined ? JSON.stringify(options.body) : undefined,
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw parseErrorBody(res.status, body, options?.fallback || "Ошибка запроса.");
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export function mapPersonnelOrdersApiError(e: unknown, fallback = "Ошибка запроса."): string {
  return formatThrownError(e, { fallback });
}

export function buildPersonnelOrdersQueryParams(
  filters: PersonnelOrdersFilters,
  options?: { includeClientSearch?: boolean; includeOrderIdInQuery?: boolean },
): URLSearchParams {
  const params = new URLSearchParams();
  const includeClientSearch = options?.includeClientSearch ?? true;

  if (filters.status?.trim()) params.set("status", filters.status.trim());
  if (filters.order_type_code?.trim()) params.set("order_type_code", filters.order_type_code.trim());
  if (filters.date_from?.trim()) params.set("date_from", filters.date_from.trim());
  if (filters.date_to?.trim()) params.set("date_to", filters.date_to.trim());
  if (filters.employee_id != null && filters.employee_id > 0) {
    params.set("employee_id", String(filters.employee_id));
  }
  if (filters.org_unit_id != null && filters.org_unit_id > 0) {
    params.set("org_unit_id", String(filters.org_unit_id));
  }
  // order_id is a UI deep-link only; not an API list filter.
  if (options?.includeOrderIdInQuery && filters.order_id != null && filters.order_id > 0) {
    params.set("order_id", String(filters.order_id));
  }
  if (includeClientSearch && filters.q?.trim()) params.set("q", filters.q.trim());
  if (filters.limit != null && filters.limit > 0) params.set("limit", String(filters.limit));
  if (filters.offset != null && filters.offset >= 0) params.set("offset", String(filters.offset));

  return params;
}

export function parsePersonnelOrdersFilters(searchParams: URLSearchParams): PersonnelOrdersFilters {
  const employeeId = Number(searchParams.get("employee_id"));
  const orderId = Number(searchParams.get("order_id"));
  const orgFilters = readTaskOrgFiltersFromSearchParams(searchParams);

  return {
    status: searchParams.get("status") || undefined,
    order_type_code: searchParams.get("order_type_code") || undefined,
    date_from: searchParams.get("date_from") || undefined,
    date_to: searchParams.get("date_to") || undefined,
    employee_id: Number.isFinite(employeeId) && employeeId > 0 ? employeeId : undefined,
    org_unit_id: orgFilters.org_unit_id,
    order_id: Number.isFinite(orderId) && orderId > 0 ? orderId : undefined,
    q: searchParams.get("q") || undefined,
  };
}

export function buildPersonnelOrdersHref(filters: PersonnelOrdersFilters = {}): string {
  const qs = buildPersonnelOrdersQueryParams(filters, { includeOrderIdInQuery: true }).toString();
  return qs ? `${PERSONNEL_ORDERS_BASE_PATH}?${qs}` : PERSONNEL_ORDERS_BASE_PATH;
}

export function filterPersonnelOrdersBySearch(
  items: PersonnelOrderListItem[],
  query: string | undefined,
): PersonnelOrderListItem[] {
  const q = String(query || "")
    .trim()
    .toLowerCase();
  if (!q) return items;
  return items.filter((row) => {
    const number = String(row.order_number || "").toLowerCase();
    const names = (row.employee_names || []).join(" ").toLowerCase();
    const ids = (row.employee_ids || []).map(String).join(" ");
    const orderId = String(row.order_id);
    return number.includes(q) || names.includes(q) || ids.includes(q) || orderId.includes(q);
  });
}

export async function listPersonnelOrders(
  filters: PersonnelOrdersFilters = {},
): Promise<PersonnelOrdersListResponse> {
  const qs = buildPersonnelOrdersQueryParams(filters, { includeClientSearch: true }).toString();
  const url = resolveApiUrl(`/directory/personnel-orders${qs ? `?${qs}` : ""}`);
  const res = await fetch(url, { method: "GET", headers: authHeaders(), cache: "no-store" });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw parseErrorBody(res.status, body, "Не удалось загрузить журнал приказов.");
  }
  return res.json() as Promise<PersonnelOrdersListResponse>;
}

export async function getPersonnelOrder(orderId: number): Promise<PersonnelOrderDetailResponse> {
  return requestJson<PersonnelOrderDetailResponse>("GET", `/directory/personnel-orders/${orderId}`, {
    fallback: "Не удалось загрузить приказ.",
  });
}

export async function getPersonnelOrderEditorial(
  orderId: number,
): Promise<PersonnelOrderEditorialState> {
  return requestJson<PersonnelOrderEditorialState>(
    "GET",
    `/directory/personnel-orders/${orderId}/editorial`,
    { fallback: "Не удалось загрузить редакционные блоки приказа." },
  );
}

export async function createPersonnelOrder(
  payload: PersonnelOrderCreatePayload,
): Promise<PersonnelOrderDetailResponse> {
  return requestJson<PersonnelOrderDetailResponse>("POST", "/directory/personnel-orders", {
    body: payload,
    fallback: "Не удалось создать приказ.",
  });
}

export async function updatePersonnelOrder(
  orderId: number,
  payload: PersonnelOrderUpdatePayload,
): Promise<PersonnelOrderDetailResponse> {
  return requestJson<PersonnelOrderDetailResponse>("PATCH", `/directory/personnel-orders/${orderId}`, {
    body: payload,
    fallback: "Не удалось обновить приказ.",
  });
}

export async function createPersonnelOrderItem(
  orderId: number,
  payload: PersonnelOrderItemCreatePayload,
): Promise<PersonnelOrderDetailResponse> {
  return requestJson<PersonnelOrderDetailResponse>("POST", `/directory/personnel-orders/${orderId}/items`, {
    body: payload,
    fallback: "Не удалось добавить пункт приказа.",
  });
}

export async function updatePersonnelOrderItem(
  orderId: number,
  itemId: number,
  payload: PersonnelOrderItemUpdatePayload,
): Promise<PersonnelOrderDetailResponse> {
  return requestJson<PersonnelOrderDetailResponse>(
    "PATCH",
    `/directory/personnel-orders/${orderId}/items/${itemId}`,
    {
      body: payload,
      fallback: "Не удалось обновить пункт приказа.",
    },
  );
}

export async function markPersonnelOrderReadyForSignature(
  orderId: number,
): Promise<PersonnelOrderDetailResponse> {
  return requestJson<PersonnelOrderDetailResponse>(
    "POST",
    `/directory/personnel-orders/${orderId}/ready-for-signature`,
    { fallback: "Не удалось перевести приказ в статус «На подписи»." },
  );
}

export async function registerPersonnelOrder(
  orderId: number,
  targetStatus: "REGISTERED" | "SIGNED" = "REGISTERED",
): Promise<PersonnelOrderDetailResponse> {
  return requestJson<PersonnelOrderDetailResponse>(
    "POST",
    `/directory/personnel-orders/${orderId}/register`,
    {
      body: { target_status: targetStatus },
      fallback: "Не удалось зарегистрировать приказ.",
    },
  );
}

export async function applyPersonnelOrder(orderId: number): Promise<PersonnelOrderDetailResponse> {
  return requestJson<PersonnelOrderDetailResponse>(
    "POST",
    `/directory/personnel-orders/${orderId}/apply`,
    { fallback: "Не удалось применить приказ." },
  );
}

export async function voidPersonnelOrder(
  orderId: number,
  voidReason: string,
): Promise<PersonnelOrderDetailResponse> {
  return requestJson<PersonnelOrderDetailResponse>("POST", `/directory/personnel-orders/${orderId}/void`, {
    body: { void_reason: voidReason },
    fallback: "Не удалось аннулировать приказ.",
  });
}
