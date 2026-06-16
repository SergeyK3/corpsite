// FILE: corpsite-ui/app/directory/personnel/_lib/importApi.client.ts
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
    return new Error("Недостаточно прав для HR Import Analytics.");
  }
  return new Error(body.trim() || fallback || `HTTP ${status}`);
}

export function mapImportApiError(e: unknown, fallback = "Ошибка запроса."): string {
  return formatThrownError(e, { fallback });
}

async function apiGetJson<T>(path: string, qs?: string): Promise<T> {
  const url = resolveApiUrl(path + (qs ? `?${qs}` : ""));
  const res = await fetch(url, { method: "GET", headers: authHeaders(), cache: "no-store" });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw parseErrorBody(res.status, body, "Не удалось загрузить данные.");
  }
  return res.json() as Promise<T>;
}

async function apiPostJson<T>(path: string): Promise<T> {
  const url = resolveApiUrl(path);
  const res = await fetch(url, { method: "POST", headers: authHeaders(true), cache: "no-store" });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw parseErrorBody(res.status, body, "Не удалось выполнить операцию.");
  }
  return res.json() as Promise<T>;
}

async function apiDeleteJson<T>(path: string): Promise<T> {
  const url = resolveApiUrl(path);
  const res = await fetch(url, { method: "DELETE", headers: authHeaders(), cache: "no-store" });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw parseErrorBody(res.status, body, "Не удалось удалить.");
  }
  return res.json() as Promise<T>;
}

export type ImportBatchRow = {
  batch_id: number;
  file_name: string;
  imported_at: string | null;
  status: string;
  total_rows: number;
  valid_rows: number;
  error_rows: number;
};

export type ImportSummary = {
  batch_id: number;
  total_rows: number;
  employee_roster_rows?: number;
  declaration_rows?: number;
  technical_category_rows?: number;
  valid_iin: number;
  by_sheet_type: Record<string, number>;
  by_declaration_group?: Record<string, number>;
  with_training: number;
  with_certification: number;
  missing_full_name: number;
  missing_iin: number;
  technical_no_iin_rows?: number;
  declaration_no_iin_rows?: number;
  invalid_iin: number;
  duplicate_iin_groups: number;
  duplicate_iin_rows: number;
};

export type AgeBucket = { key: string; label: string; count: number };

export type DepartmentRow = {
  department: string;
  total: number;
  doctors: number;
  nurses: number;
  junior_staff: number;
  other: number;
  with_training: number;
  with_certification: number;
  age_65_plus: number;
  average_age: number | null;
};

export type PositionRow = { position: string; count: number };

export type RiskRow = {
  risk_type: string;
  label: string;
  count: number;
  row_ids: number[];
};

export type StagingRow = {
  row_id: number;
  full_name: string;
  iin_masked: string;
  birth_date: string;
  age: number | null;
  department: string;
  position_raw: string;
  training_raw: string;
  certification_raw: string;
  source_sheet: string;
  source_row_number: number;
  sheet_type: string;
  classification: string;
  row_type?: string;
  declaration_group?: string;
  is_employee_roster?: boolean;
};

export type DocumentCandidate = {
  candidate_id: number;
  batch_id: number;
  row_id: number;
  employee_id: number | null;
  employee_identity_id: number | null;
  full_name: string;
  iin_masked: string;
  department: string;
  position: string;
  document_type: string;
  document_kind: string;
  title: string;
  organization: string;
  issued_at: string | null;
  valid_until: string | null;
  hours: number | null;
  specialty: string;
  category: string;
  certificate_number: string;
  raw_text: string;
  source_sheet: string;
  source_row: number | null;
  external_url: string;
  storage_type: string;
  storage_path: string;
  status: string;
  fragment_index: number;
  confidence_score: number | null;
  parse_method: string;
  source_field: string;
};

export type DocumentCandidatesSummary = {
  batch_id: number;
  total_candidates: number;
  by_kind: { training: number; certification: number; education?: number };
  by_status: Record<string, number>;
};

export type EmployeeTrainingHistory = {
  batch_id: number;
  employee: {
    row_id: number;
    employee_id: number | null;
    full_name: string;
    iin_masked: string;
    department: string;
    position: string;
  };
  items: DocumentCandidate[];
};

export type SheetDiagnosticRow = {
  sheet_name: string;
  sheet_type: string;
  rows_total: number;
  employee_rows: number;
  declaration_rows: number;
  technical_rows: number;
  candidates_count: number;
};

export type SheetDiagnostics = {
  batch_id: number;
  items: SheetDiagnosticRow[];
  totals: {
    rows_total: number;
    employee_rows: number;
    declaration_rows: number;
    technical_rows: number;
    candidates_count: number;
  };
};

export type RebuildCandidatesResult = {
  batch_id: number;
  deleted_candidates: number;
  preserved_candidates: number;
  training_candidates: number;
  certification_candidates: number;
  education_candidates: number;
  total_candidates: number;
  skipped?: boolean;
};

export type DeleteBatchResult = {
  batch_id: number;
  deleted: boolean;
  deleted_rows: number;
  deleted_candidates: number;
};

export async function getDocumentCandidatesSummary(batchId: number): Promise<DocumentCandidatesSummary> {
  return apiGetJson(`/directory/personnel/import/batches/${batchId}/document-candidates/summary`);
}

export async function listDocumentCandidates(
  batchId: number,
  params: Record<string, string | number | boolean | null | undefined> = {}
): Promise<{ total: number; items: DocumentCandidate[]; limit: number; offset: number }> {
  return apiGetJson(`/directory/personnel/import/batches/${batchId}/document-candidates`, buildQuery(params));
}

export async function getEmployeeTrainingHistory(
  batchId: number,
  rowId: number
): Promise<EmployeeTrainingHistory> {
  return apiGetJson(`/directory/personnel/import/batches/${batchId}/document-candidates/employees/${rowId}`);
}

export async function listImportBatches(): Promise<{ items: ImportBatchRow[] }> {
  return apiGetJson("/directory/personnel/import/batches");
}

export async function deleteImportBatch(batchId: number): Promise<DeleteBatchResult> {
  return apiDeleteJson(`/directory/personnel/import/batches/${batchId}`);
}

export async function rebuildDocumentCandidates(batchId: number): Promise<RebuildCandidatesResult> {
  return apiPostJson(`/directory/personnel/import/batches/${batchId}/document-candidates/rebuild`);
}

export async function getSheetDiagnostics(batchId: number): Promise<SheetDiagnostics> {
  return apiGetJson(`/directory/personnel/import/batches/${batchId}/sheet-diagnostics`);
}

export async function getImportSummary(batchId: number): Promise<ImportSummary> {
  return apiGetJson(`/directory/personnel/import/batches/${batchId}/summary`);
}

export async function getAgeDistribution(batchId: number): Promise<{ buckets: AgeBucket[]; unknown: number }> {
  return apiGetJson(`/directory/personnel/import/batches/${batchId}/age-distribution`);
}

export async function getDepartmentAnalytics(batchId: number): Promise<{ items: DepartmentRow[] }> {
  return apiGetJson(`/directory/personnel/import/batches/${batchId}/departments`);
}

export async function getPositionAnalytics(batchId: number): Promise<{ items: PositionRow[] }> {
  return apiGetJson(`/directory/personnel/import/batches/${batchId}/positions`);
}

export async function getTrainingAnalytics(batchId: number): Promise<{
  total_with_training: number;
  by_department: { department: string; count: number }[];
  examples: { row_id: number; full_name: string; department: string; training_raw: string }[];
}> {
  return apiGetJson(`/directory/personnel/import/batches/${batchId}/training`);
}

export async function getCertificationAnalytics(batchId: number): Promise<{
  total_with_certification: number;
  by_group: { group: string; label: string; count: number }[];
  examples: { row_id: number; full_name: string; department: string; certification_raw: string; group: string }[];
}> {
  return apiGetJson(`/directory/personnel/import/batches/${batchId}/certification`);
}

export async function getRiskAnalytics(batchId: number): Promise<{ items: RiskRow[] }> {
  return apiGetJson(`/directory/personnel/import/batches/${batchId}/risks`);
}

export async function listStagingRows(
  batchId: number,
  params: Record<string, string | number | boolean | null | undefined> = {}
): Promise<{ total: number; items: StagingRow[]; limit: number; offset: number }> {
  return apiGetJson(`/directory/personnel/import/batches/${batchId}/rows`, buildQuery(params));
}

export async function uploadControlList(file: File): Promise<{
  batch_id: number;
  file_name: string;
  summary: ImportSummary;
  warnings: string[];
}> {
  const url = resolveApiUrl("/directory/personnel/import/upload");
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(url, {
    method: "POST",
    headers: authHeaders(),
    body: form,
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw parseErrorBody(res.status, body, "Не удалось загрузить файл.");
  }
  return res.json();
}

export const SHEET_TYPE_LABELS: Record<string, string> = {
  doctors: "Врачи",
  nurses: "Медсестра / СМР",
  junior_staff: "Младший персонал",
  other_staff: "Прочие",
  part_time: "Совместители",
  declaration: "Декларации",
};
