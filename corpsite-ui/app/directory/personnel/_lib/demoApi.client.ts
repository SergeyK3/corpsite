// FILE: corpsite-ui/app/directory/personnel/_lib/demoApi.client.ts
import { getSessionAccessToken } from "@/lib/auth";
import { formatThrownError } from "@/lib/i18n";

function getApiBase(): string {
  const v = (process.env.NEXT_PUBLIC_API_BASE_URL || "").trim().replace(/\/+$/, "");
  return v || "http://127.0.0.1:8000";
}

function getDevUserId(): string | null {
  const appEnv = (process.env.NEXT_PUBLIC_APP_ENV || "dev").trim().toLowerCase();
  if (appEnv === "prod" || appEnv === "production") return null;
  const v = (process.env.NEXT_PUBLIC_DEV_X_USER_ID || "").trim();
  return v ? v : null;
}

function buildQuery(params: Record<string, string | number | null | undefined>): string {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === null) return;
    const s = String(v).trim();
    if (!s) return;
    q.set(k, s);
  });
  return q.toString();
}

export function mapDemoApiError(e: unknown, fallback = "Ошибка запроса."): string {
  return formatThrownError(e, { fallback });
}

async function apiGetJson<T>(path: string, qs?: string): Promise<T> {
  const apiBase = getApiBase();
  const devUserId = getDevUserId();
  const headers: Record<string, string> = { Accept: "application/json" };
  if (devUserId) headers["X-User-Id"] = devUserId;
  const token = String(getSessionAccessToken?.() ?? "").trim();
  if (token) headers.Authorization = `Bearer ${token}`;

  const url = qs ? `${apiBase}${path}?${qs}` : `${apiBase}${path}`;
  const res = await fetch(url, { method: "GET", headers, cache: "no-store" });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status}: ${body || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export type PersonnelEventRow = {
  event_id: number;
  employee_id: number;
  employee_name: string;
  event_type: string;
  effective_date: string;
  from_org_unit_id: number | null;
  from_org_unit_name: string | null;
  to_org_unit_id: number | null;
  to_org_unit_name: string | null;
  order_ref: string | null;
};

export type PersonnelEventsResponse = {
  items: PersonnelEventRow[];
  total: number;
};

export async function listPersonnelEvents(args?: {
  event_type?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}): Promise<PersonnelEventsResponse> {
  const qs = buildQuery({
    event_type: args?.event_type,
    date_from: args?.date_from,
    date_to: args?.date_to,
    limit: args?.limit ?? 100,
    offset: args?.offset ?? 0,
  });
  return apiGetJson<PersonnelEventsResponse>("/directory/personnel-events", qs);
}

export type ProfessionalDocumentRow = {
  certificate_id: number | null;
  employee_id: number;
  employee_name: string;
  certificate_type_name: string;
  expires_at: string | null;
  status: "VALID" | "EXPIRING_60" | "EXPIRING_30" | "EXPIRED" | "MISSING" | string;
};

export type ProfessionalDocumentsResponse = {
  items: ProfessionalDocumentRow[];
  total: number;
};

export async function listProfessionalDocuments(): Promise<ProfessionalDocumentsResponse> {
  return apiGetJson<ProfessionalDocumentsResponse>("/directory/professional-documents");
}
