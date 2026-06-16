// FILE: corpsite-ui/app/directory/personnel/_lib/documentsApi.client.ts
import { getSessionAccessToken } from "@/lib/auth";
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
  const headers: Record<string, string> = { Accept: "application/json" };
  if (json) headers["Content-Type"] = "application/json";
  const devUserId = getDevUserId();
  if (devUserId) headers["X-User-Id"] = devUserId;
  const token = String(getSessionAccessToken?.() ?? "").trim();
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

function parseErrorBody(status: number, body: string, fallback: string): Error {
  if (status === 403) {
    return new Error("Недостаточно прав для работы с реестром документов.");
  }
  if (status === 422) {
    try {
      const parsed = JSON.parse(body) as { detail?: unknown };
      if (typeof parsed.detail === "string" && parsed.detail.trim()) {
        return new Error(parsed.detail);
      }
    } catch {
      /* ignore */
    }
    return new Error("Проверьте заполнение полей формы.");
  }
  return new Error(body.trim() || fallback || `HTTP ${status}`);
}

export function mapDocumentsApiError(e: unknown, fallback = "Ошибка запроса."): string {
  return formatThrownError(e, { fallback });
}

async function apiRequest<T>(
  path: string,
  init: RequestInit,
  fallback: string
): Promise<T> {
  const url = resolveApiUrl(path);
  const res = await fetch(url, { ...init, cache: "no-store" });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw parseErrorBody(res.status, body, fallback);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}

async function apiGetJson<T>(path: string, qs?: string): Promise<T> {
  const suffix = qs ? `?${qs}` : "";
  return apiRequest<T>(path + suffix, { method: "GET", headers: authHeaders() }, "Не удалось загрузить данные.");
}

async function apiPostJson<T>(path: string, body: unknown): Promise<T> {
  return apiRequest<T>(
    path,
    { method: "POST", headers: authHeaders(true), body: JSON.stringify(body) },
    "Не удалось создать документ."
  );
}

async function apiPutJson<T>(path: string, body: unknown): Promise<T> {
  return apiRequest<T>(
    path,
    { method: "PUT", headers: authHeaders(true), body: JSON.stringify(body) },
    "Не удалось обновить документ."
  );
}

async function apiDeleteJson<T>(path: string): Promise<T> {
  return apiRequest<T>(
    path,
    { method: "DELETE", headers: authHeaders() },
    "Не удалось архивировать документ."
  );
}

export type DocumentTypeRow = {
  document_type_id: number;
  code: string;
  name: string;
  category: string;
  has_valid_until: boolean;
  requires_medical_specialty: boolean;
  tracks_hours: boolean;
  is_active: boolean;
  sort_order: number;
};

export type DocumentKindRow = {
  document_kind_id: number;
  code: string;
  name: string;
  is_active: boolean;
  sort_order: number;
};

export type MedicalSpecialtyGroupRow = {
  group_id: number;
  code: string;
  name: string;
  is_active: boolean;
};

export type MedicalSpecialtyRow = {
  medical_specialty_id: number;
  group_id: number;
  group_code: string;
  code: string;
  name: string;
  is_active: boolean;
};

export type EmployeeDocumentRow = {
  document_id: number;
  employee_id: number;
  employee_name: string;
  employee_is_active?: boolean;
  document_type_id: number;
  document_type_code: string;
  document_type_name: string;
  document_kind_id: number | null;
  document_kind_code: string | null;
  document_kind_name: string | null;
  medical_specialty_id: number | null;
  medical_specialty_name: string | null;
  medical_specialty_group_id?: number | null;
  title: string | null;
  training_title: string | null;
  document_number: string | null;
  issued_by: string | null;
  issued_at: string | null;
  valid_until: string | null;
  file_url: string | null;
  comment: string | null;
  lifecycle_status: string;
  expiry_status: string;
  created_by?: number;
  created_at?: string;
  updated_at?: string;
};

export type ListResponse<T> = {
  items: T[];
  total: number;
};

export type EmployeeDocumentCreatePayload = {
  employee_id: number;
  document_type_id: number;
  document_kind_id?: number | null;
  medical_specialty_id?: number | null;
  title?: string | null;
  training_title?: string | null;
  document_number?: string | null;
  issued_by?: string | null;
  issued_at?: string | null;
  valid_until?: string | null;
  file_url?: string | null;
  comment?: string | null;
};

export type EmployeeDocumentUpdatePayload = {
  document_type_id?: number;
  document_kind_id?: number | null;
  clear_document_kind?: boolean;
  medical_specialty_id?: number | null;
  clear_medical_specialty?: boolean;
  title?: string | null;
  training_title?: string | null;
  document_number?: string | null;
  issued_by?: string | null;
  issued_at?: string | null;
  valid_until?: string | null;
  clear_valid_until?: boolean;
  file_url?: string | null;
  clear_file_url?: boolean;
  comment?: string | null;
};

export async function listDocumentTypes(isActive = true): Promise<ListResponse<DocumentTypeRow>> {
  const qs = buildQuery({ is_active: isActive });
  return apiGetJson<ListResponse<DocumentTypeRow>>("/directory/document-types", qs);
}

export async function listDocumentKinds(isActive = true): Promise<ListResponse<DocumentKindRow>> {
  const qs = buildQuery({ is_active: isActive });
  return apiGetJson<ListResponse<DocumentKindRow>>("/directory/document-kinds", qs);
}

export async function listMedicalSpecialtyGroups(): Promise<ListResponse<MedicalSpecialtyGroupRow>> {
  return apiGetJson<ListResponse<MedicalSpecialtyGroupRow>>("/directory/medical-specialty-groups");
}

export async function listMedicalSpecialties(args?: {
  group_id?: number;
  group_code?: string;
  is_active?: boolean;
}): Promise<ListResponse<MedicalSpecialtyRow>> {
  const qs = buildQuery({
    group_id: args?.group_id,
    group_code: args?.group_code,
    is_active: args?.is_active ?? true,
  });
  return apiGetJson<ListResponse<MedicalSpecialtyRow>>("/directory/medical-specialties", qs);
}

export async function listEmployeeDocuments(args?: {
  employee_id?: number;
  employee_is_active?: boolean;
  document_type_id?: number;
  medical_specialty_id?: number;
  group_id?: number;
  lifecycle_status?: string;
  expiry_status?: string;
  q?: string;
  limit?: number;
  offset?: number;
}): Promise<ListResponse<EmployeeDocumentRow>> {
  const qs = buildQuery({
    employee_id: args?.employee_id,
    employee_is_active: args?.employee_is_active,
    document_type_id: args?.document_type_id,
    medical_specialty_id: args?.medical_specialty_id,
    group_id: args?.group_id,
    lifecycle_status: args?.lifecycle_status ?? "ACTIVE",
    expiry_status: args?.expiry_status,
    q: args?.q,
    limit: args?.limit ?? 500,
    offset: args?.offset ?? 0,
  });
  return apiGetJson<ListResponse<EmployeeDocumentRow>>("/directory/employee-documents", qs);
}

export async function getEmployeeDocument(documentId: number): Promise<EmployeeDocumentRow> {
  return apiGetJson<EmployeeDocumentRow>(
    `/directory/employee-documents/${encodeURIComponent(String(documentId))}`
  );
}

export async function createEmployeeDocument(
  payload: EmployeeDocumentCreatePayload
): Promise<EmployeeDocumentRow> {
  return apiPostJson<EmployeeDocumentRow>("/directory/employee-documents", payload);
}

export async function updateEmployeeDocument(
  documentId: number,
  payload: EmployeeDocumentUpdatePayload
): Promise<EmployeeDocumentRow> {
  return apiPutJson<EmployeeDocumentRow>(
    `/directory/employee-documents/${encodeURIComponent(String(documentId))}`,
    payload
  );
}

export async function archiveEmployeeDocument(
  documentId: number
): Promise<{ document_id: number; lifecycle_status: string }> {
  return apiDeleteJson<{ document_id: number; lifecycle_status: string }>(
    `/directory/employee-documents/${encodeURIComponent(String(documentId))}`
  );
}

export function isHttpUrl(value: string | null | undefined): boolean {
  const v = String(value || "").trim();
  return /^https?:\/\//i.test(v);
}
