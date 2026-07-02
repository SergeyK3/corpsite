// FILE: corpsite-ui/app/directory/personnel/_lib/importApi.client.ts
import { buildHeaders } from "@/lib/api";
import { formatThrownError } from "@/lib/i18n";
import { resolveApiUrl } from "@/lib/apiBase";
import type { FieldDiffEntry, MonthlyDiffStatus } from "./monthlyDiffLabels";

export type { FieldDiffEntry, MonthlyDiffStatus } from "./monthlyDiffLabels";

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
  if (status === 403) {
    return new Error("Недостаточно прав для HR Import Analytics.");
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

async function apiPostJson<T>(path: string, body?: unknown): Promise<T> {
  const url = resolveApiUrl(path);
  const res = await fetch(url, {
    method: "POST",
    headers: authHeaders(true),
    body: body !== undefined ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw parseErrorBody(res.status, text, "Не удалось выполнить операцию.");
  }
  return res.json() as Promise<T>;
}

async function apiPatchJson<T>(path: string, body: unknown): Promise<T> {
  const url = resolveApiUrl(path);
  const res = await fetch(url, {
    method: "PATCH",
    headers: authHeaders(true),
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw parseErrorBody(res.status, text, "Не удалось сохранить.");
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
  /** Present when requested via ?with_normalized_records=true */
  normalized_record_count?: number;
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
  iin: string;
  birth_date: string;
  age: number | null;
  department: string;
  org_unit_id?: number | null;
  org_unit_name?: string;
  org_group_id?: number | null;
  department_group?: string;
  effective_log_group?: string | null;
  effective_log_group_name?: string | null;
  position_raw: string;
  training_raw: string;
  certification_raw: string;
  certification_group?: string;
  latest_medical_category?: string;
  latest_medical_category_date?: string;
  staff_type?: string;
  is_part_time?: boolean;
  source_sheet: string;
  source_row_number: number;
  sheet_type: string;
  classification: string;
  row_type?: string;
  declaration_group?: string;
  is_employee_roster?: boolean;
  diff_status?: MonthlyDiffStatus | null;
  canonical_snapshot_id?: number | null;
  canonical_entry_id?: number | null;
  canonical_hash?: string | null;
  field_diffs?: Record<string, FieldDiffEntry> | null;
  diff_computed_at?: string | null;
};

export type DepartmentRecodingOptions = {
  groups: {
    value: string;
    label: string;
    group_id?: number;
    effective_log_group?: string;
    effective_log_group_name?: string;
  }[];
  departments: {
    org_unit_id: number | null;
    org_unit_name: string;
    org_group_id: number;
  }[];
};

export type PortfolioRecord = {
  source_field: string;
  source_text: string;
  confidence: number;
  parse_method: string;
  document_id: number | null;
};

export type DegreePortfolioRecord = PortfolioRecord & {
  degree_type?: string;
  label: string;
  completed_at?: string;
};

export type EducationPortfolioRecord = PortfolioRecord & {
  record_type: string;
  institution: string;
  specialty: string;
  completed_at: string;
};

export type TrainingPortfolioRecord = PortfolioRecord & {
  title: string;
  organization: string;
  hours: number | null;
  started_at: string;
  completed_at: string;
};

export type CategoryPortfolioRecord = PortfolioRecord & {
  category: string;
  specialty: string;
  issued_at: string;
};

export type CertificatePortfolioRecord = PortfolioRecord & {
  kind?: string;
  topic?: string;
  specialty: string;
  issued_at: string;
  valid_until: string;
  hours?: number | null;
  link?: string;
  certificate_number: string;
};

export type EducationProfileSummary = {
  profile_id: number;
  aggregate_key?: string;
  batch_id: number;
  row_id: number;
  source_row_ids?: number[];
  employee_id: number | null;
  full_name: string;
  iin: string;
  department_source: string;
  org_unit_id: number | null;
  org_unit_name: string;
  org_group_id?: number | null;
  department_group: string;
  effective_log_group?: string | null;
  effective_log_group_name?: string | null;
  position_raw: string;
  education_count: number;
  training_count: number;
  certificate_count: number;
  category_count: number;
  award_count: number;
  profile_status: string;
  review_status: string;
  review_status_label: string;
};

export type EducationProfileDetail = {
  profile_id: number;
  aggregate_key?: string;
  batch_id: number;
  row_id: number;
  source_row_ids?: number[];
  employee_id: number | null;
  source_sheet: string;
  source_row_number: number;
  full_name: string;
  iin: string;
  profile_status: string;
  review_status: string;
  review_status_label: string;
  department_recoding: {
    org_unit_id: number | null;
    org_unit_name: string;
    department_group: string;
  } | null;
  profile: ImportProfile & { notes_raw?: string; status?: string; review_status?: string };
};

export type AwardPortfolioRecord = PortfolioRecord & {
  title: string;
  date: string;
};

export type ImportProfile = {
  basic: {
    full_name: string;
    iin: string;
    birth_date: string;
    sex: string;
    position_raw: string;
    department_source: string;
    experience_raw: string;
    employment_rate: number | null;
    qualification_raw: string;
    nationality: string;
    phone_raw: string;
  };
  education: Record<string, EducationPortfolioRecord[]>;
  education_records: EducationPortfolioRecord[];
  training_records: TrainingPortfolioRecord[];
  category_records: CategoryPortfolioRecord[];
  certificate_records: CertificatePortfolioRecord[];
  award_records: AwardPortfolioRecord[];
  degrees: {
    candidate_medical_sciences: boolean;
    doctor_medical_sciences: boolean;
    raw_text: string;
    records: DegreePortfolioRecord[];
  };
  portfolio_totals: Record<string, number>;
  notes_raw?: string;
  status?: string;
  review_status?: string;
};

const EMPTY_IMPORT_PROFILE_BASIC: ImportProfile["basic"] = {
  full_name: "",
  iin: "",
  birth_date: "",
  sex: "",
  position_raw: "",
  department_source: "",
  experience_raw: "",
  employment_rate: null,
  qualification_raw: "",
  nationality: "",
  phone_raw: "",
};

export function normalizeImportProfile(profile: ImportProfile | null | undefined): ImportProfile {
  const source = profile ?? ({} as ImportProfile);
  return {
    basic: { ...EMPTY_IMPORT_PROFILE_BASIC, ...(source.basic ?? {}) },
    education: source.education ?? {},
    education_records: Array.isArray(source.education_records) ? source.education_records : [],
    training_records: Array.isArray(source.training_records) ? source.training_records : [],
    category_records: Array.isArray(source.category_records) ? source.category_records : [],
    certificate_records: Array.isArray(source.certificate_records) ? source.certificate_records : [],
    award_records: Array.isArray(source.award_records) ? source.award_records : [],
    degrees: {
      candidate_medical_sciences: Boolean(source.degrees?.candidate_medical_sciences),
      doctor_medical_sciences: Boolean(source.degrees?.doctor_medical_sciences),
      raw_text: String(source.degrees?.raw_text ?? ""),
      records: Array.isArray(source.degrees?.records) ? source.degrees.records : [],
    },
    portfolio_totals: source.portfolio_totals ?? {},
    notes_raw: source.notes_raw ?? "",
    status: source.status,
    review_status: source.review_status,
  };
}

export function cloneImportProfile(profile: ImportProfile): ImportProfile {
  return normalizeImportProfile(JSON.parse(JSON.stringify(profile)) as ImportProfile);
}

export type AiExtractionDraft = {
  draft_id?: number;
  batch_id?: number;
  row_id?: number;
  parse_method: string;
  status: string;
  requires_review: boolean;
  review_label: string;
  extraction: {
    education: Array<Record<string, unknown>>;
    training: Array<Record<string, unknown>>;
    certificates: Array<Record<string, unknown>>;
    categories: Array<Record<string, unknown>>;
    awards: Array<Record<string, unknown>>;
    degrees: Array<Record<string, unknown>>;
    warnings: string[];
  };
  created_at?: string | null;
  updated_at?: string | null;
};

export type RowReviewDetail = {
  batch_id: number;
  row_id: number;
  employee_id?: number | null;
  full_name: string;
  iin: string;
  birth_date: string;
  sex: string;
  employment_rate: number | null;
  department: string;
  department_source: string;
  department_recoding: {
    org_unit_id: number | null;
    org_unit_name: string;
    department_group: string;
  } | null;
  position_raw: string;
  staff_type: string;
  is_part_time: boolean;
  sheet_type: string;
  classification: string;
  declaration_group: string;
  profile: ImportProfile;
  education: { institution: string; year: string; specialty: string; raw_text: string }[];
  experience_raw: string;
  training: { title: string; year: string; hours: number | null; raw_text: string }[];
  qualification_categories: {
    category: string;
    date: string;
    specialty: string;
    raw_text: string;
    document_type: string;
  }[];
  certificates: {
    kind: string;
    topic: string;
    date: string;
    valid_until?: string;
    hours: number | null;
    link: string;
    raw_text: string;
  }[];
  degrees: {
    candidate_medical_sciences: boolean;
    doctor_medical_sciences: boolean;
    raw_text: string;
  };
  awards: { title: string; date: string }[];
  notes: string[];
  ai_extraction: AiExtractionDraft | null;
  source_sheet: string;
  source_row_number: number;
  diff_status?: MonthlyDiffStatus | null;
  canonical_snapshot_id?: number | null;
  canonical_entry_id?: number | null;
  canonical_hash?: string | null;
  field_diffs?: Record<string, FieldDiffEntry> | null;
  diff_computed_at?: string | null;
};

export type EducationPortfolio = {
  batch_id: number;
  education: DocumentCandidate[];
  training: DocumentCandidate[];
  categories: DocumentCandidate[];
  certificates: DocumentCandidate[];
  awards: DocumentCandidate[];
  totals: {
    education: number;
    training: number;
    categories: number;
    certificates: number;
    awards: number;
  };
};

export type DocumentCandidate = {
  candidate_id: number;
  batch_id: number;
  row_id: number;
  employee_id: number | null;
  employee_identity_id: number | null;
  full_name: string;
  iin: string;
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
    iin: string;
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

export async function listImportBatches(options?: {
  withNormalizedRecords?: boolean;
}): Promise<{ items: ImportBatchRow[] }> {
  const query = buildQuery({
    with_normalized_records: options?.withNormalizedRecords ? true : undefined,
  });
  const path = query
    ? `/directory/personnel/import/batches?${query}`
    : "/directory/personnel/import/batches";
  return apiGetJson(path);
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

export async function getDepartmentRecodingOptions(): Promise<DepartmentRecodingOptions> {
  return apiGetJson("/directory/personnel/import/department-recoding/options");
}

export type EmployeeImportCard2Detail = {
  batch_id: number;
  row_id: number;
  profile_id: number;
  employee_id: number;
  card_batch_id: number;
  latest_batch_id: number | null;
  missing_from_latest_import: boolean;
  base_batch_id: number | null;
  base_row_id: number | null;
  base_imported_at: string | null;
  created_by: number | null;
  updated_by: number | null;
  source_sheet: string;
  source_row_number: number;
  full_name: string;
  department_source: string;
  department_recoding: {
    org_unit_id: number | null;
    org_unit_name: string;
    department_group: string;
  } | null;
  position_raw: string;
  sheet_type: string;
  profile: ImportProfile;
  profile_status: string;
  review_status: string;
  has_override: boolean;
};

export async function getEmployeeImportCard2(employeeId: string | number): Promise<EmployeeImportCard2Detail> {
  return apiGetJson(`/directory/personnel/employees/${encodeURIComponent(String(employeeId))}/import-card`);
}

export async function saveEmployeeImportCard2(
  employeeId: string | number,
  profile: ImportProfile
): Promise<EmployeeImportCard2Detail> {
  return apiPatchJson(`/directory/personnel/employees/${encodeURIComponent(String(employeeId))}/import-card`, {
    profile,
  });
}

export async function deleteEmployeeImportCard2(employeeId: string | number): Promise<EmployeeImportCard2Detail> {
  return apiDeleteJson(`/directory/personnel/employees/${encodeURIComponent(String(employeeId))}/import-card`);
}

export async function getRowReviewDetail(batchId: number, rowId: number): Promise<RowReviewDetail> {
  return apiGetJson(`/directory/personnel/import/batches/${batchId}/rows/${rowId}/review`);
}

export type RowMedicalCategoryHistoryItem = {
  date: string;
  category: string;
  category_label: string;
  specialty: string;
  validity_note?: string;
};

export type RowMedicalCategoryHistory = {
  batch_id: number;
  row_id: number;
  full_name: string;
  position_raw: string;
  department: string;
  org_unit_name: string;
  items: RowMedicalCategoryHistoryItem[];
};

export async function getRowMedicalCategoryHistory(
  batchId: number,
  rowId: number
): Promise<RowMedicalCategoryHistory> {
  return apiGetJson(
    `/directory/personnel/import/batches/${batchId}/rows/${rowId}/medical-categories`
  );
}

export async function runRowAiExtraction(batchId: number, rowId: number): Promise<AiExtractionDraft> {
  return apiPostJson(`/directory/personnel/import/batches/${batchId}/rows/${rowId}/ai-extraction`);
}

export async function listEducationProfiles(
  batchId: number,
  params: Record<string, string | number | boolean | null | undefined> = {}
): Promise<{ batch_id: number; total: number; items: EducationProfileSummary[]; limit: number; offset: number }> {
  return apiGetJson(`/directory/personnel/import/batches/${batchId}/education-profiles`, buildQuery(params));
}

export async function getEducationProfileDetail(
  batchId: number,
  profileId: number
): Promise<EducationProfileDetail> {
  return apiGetJson(`/directory/personnel/import/batches/${batchId}/education-profiles/${profileId}`);
}

export async function saveEducationProfile(
  batchId: number,
  profileId: number,
  body: { profile?: ImportProfile; review_status?: string; profile_status?: string }
): Promise<EducationProfileDetail> {
  return apiPatchJson(`/directory/personnel/import/batches/${batchId}/education-profiles/${profileId}`, body);
}

export async function archiveEducationProfile(
  batchId: number,
  profileId: number
): Promise<EducationProfileDetail> {
  return apiPostJson(`/directory/personnel/import/batches/${batchId}/education-profiles/${profileId}/archive`);
}

/** Parse org group filter: slug (effective_log_group) or legacy numeric org_group_id. */
export function parseGroupFilterValue(value: string): {
  effective_log_group?: string;
  org_group_id?: number;
} {
  const v = value.trim();
  if (!v) return {};
  const id = Number(v);
  if (Number.isFinite(id) && id > 0 && /^\d+$/.test(v)) return { org_group_id: id };
  return { effective_log_group: v };
}

export function resolveGroupIdFromOptions(
  options: DepartmentRecodingOptions | null,
  selectedValue: string,
): number | undefined {
  const v = selectedValue.trim();
  if (!v) return undefined;
  const matched = options?.groups.find((g) => g.value === v);
  if (matched?.group_id != null && matched.group_id > 0) return matched.group_id;
  const id = Number(v);
  return Number.isFinite(id) && id > 0 ? id : undefined;
}

/** Parse department filter value from dropdown (id or name: prefix). */
export function parseDepartmentFilterValue(value: string): {
  org_unit_id?: number;
  org_unit_name?: string;
} {
  const v = value.trim();
  if (!v) return {};
  if (v.startsWith("name:")) return { org_unit_name: v.slice(5) };
  const id = Number(v);
  return Number.isFinite(id) ? { org_unit_id: id } : {};
}

export function departmentFilterOptionValue(d: {
  org_unit_id: number | null;
  org_unit_name: string;
}): string {
  return d.org_unit_id != null ? String(d.org_unit_id) : `name:${d.org_unit_name}`;
}

export async function getEducationPortfolio(batchId: number): Promise<EducationPortfolio> {
  return apiGetJson(`/directory/personnel/import/batches/${batchId}/education-portfolio`);
}

export function getDeclarationsExportUrl(
  batchId: number,
  params: Record<string, string | number | undefined> = {}
): string {
  const q = buildQuery(params as Record<string, string | number | boolean | null | undefined>);
  return resolveApiUrl(
    `/directory/personnel/import/batches/${batchId}/declarations/export${q ? `?${q}` : ""}`
  );
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
): Promise<{
  total: number;
  items: StagingRow[];
  limit: number;
  offset: number;
  hide_unchanged?: boolean;
}> {
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

export type NormalizedRecordReviewStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "promoted"
  | "superseded";

export type {
  NormalizedRecordKind,
} from "./normalizedRecordLabels";

export {
  NORMALIZED_RECORD_KINDS,
  NORMALIZED_RECORD_KIND_LABELS,
  NORMALIZED_RECORD_KIND_SUMMARY_LABELS,
  getNormalizedRecordKindLabel,
  getNormalizedRecordKindSummaryLabel,
  isNormalizedRecordKind,
} from "./normalizedRecordLabels";

import type { NormalizedRecordKind } from "./normalizedRecordLabels";
import type { EmployeeBindingInfo } from "./normalizedRecordBindingLabels";

export type {
  EmployeeBindingInfo,
  EmployeeBindingStatus,
  EmployeeBindingMethod,
} from "./normalizedRecordBindingLabels";

export {
  EMPLOYEE_BINDING_STATUS_LABELS,
  EMPLOYEE_BINDING_METHOD_LABELS,
  employeeBindingBadgeClass,
} from "./normalizedRecordBindingLabels";

export type NormalizedRecordSummary = {
  total: number;
  pending: number;
  approved: number;
  rejected: number;
  promoted: number;
  superseded: number;
  by_kind: Record<NormalizedRecordKind, number>;
  skipped?: boolean;
};

export type NormalizedRecordPayloadValues = {
  title: string | null;
  provider: string | null;
  hours: number | null;
  start_date: string | null;
  end_date: string | null;
  issue_date: string | null;
  expiry_date: string | null;
  document_number: string | null;
  specialty_text: string | null;
  medical_specialty_id: number | null;
  file_url: string | null;
};

export type NormalizedRecordReviewOverride = Partial<NormalizedRecordPayloadValues>;

export type NormalizedRecord = {
  record_id: number;
  normalized_record_id: number;
  batch_id: number;
  row_id: number;
  employee_id: number | null;
  employee_binding?: EmployeeBindingInfo;
  full_name: string;
  iin: string;
  fragment_index: number;
  source_field: string;
  source_text: string;
  source_record_key: string;
  record_kind: NormalizedRecordKind;
  document_type_id: number | null;
  document_type_code: string | null;
  title: string | null;
  provider: string | null;
  hours: number | null;
  start_date: string | null;
  end_date: string | null;
  issue_date: string | null;
  expiry_date: string | null;
  document_number: string | null;
  specialty_text: string | null;
  medical_specialty_id: number | null;
  file_url: string | null;
  parsed_values?: NormalizedRecordPayloadValues;
  review_override?: NormalizedRecordReviewOverride | null;
  review_override_updated_by?: number | null;
  review_override_updated_at?: string | null;
  parse_method: string;
  confidence: number | null;
  review_status: NormalizedRecordReviewStatus;
  reviewed_at: string | null;
  reviewed_by: number | null;
  review_notes: string | null;
  promoted_document_id: number | null;
  promoted_at: string | null;
  promoted_by: number | null;
  created_at: string | null;
  updated_at: string | null;
  diff_status?: MonthlyDiffStatus | null;
  canonical_snapshot_id?: number | null;
  canonical_entry_id?: number | null;
  canonical_hash?: string | null;
  field_diffs?: Record<string, FieldDiffEntry> | null;
  diff_computed_at?: string | null;
};

export type MonthlyDiffRemoval = {
  removal_id?: number;
  canonical_entry_id: number;
  match_key: string;
  record_kind: string;
  canonical_hash?: string;
  payload?: Record<string, unknown> | null;
  diff_status: "REMOVED";
  diff_computed_at?: string | null;
};

export type ImportBatchReviewVisibility = {
  visible_records: number;
  hidden_unchanged: number;
  no_changes_detected: boolean;
  review_complete: boolean;
};

export type ImportBatchDiffSummary = {
  batch_id: number;
  snapshot_id: number | null;
  computed_at: string | null;
  summary: Partial<Record<MonthlyDiffStatus, number>>;
  removed: MonthlyDiffRemoval[];
  skipped: boolean;
  review_visibility?: ImportBatchReviewVisibility;
};

export async function getImportBatchDiffSummary(batchId: number): Promise<ImportBatchDiffSummary> {
  return apiGetJson(`/directory/personnel/import/batches/${batchId}/diff-summary`);
}

export async function computeImportBatchDiff(batchId: number): Promise<ImportBatchDiffSummary> {
  return apiPostJson(`/directory/personnel/import/batches/${batchId}/compute-diff`);
}

export async function getNormalizedRecordsSummary(batchId?: number): Promise<NormalizedRecordSummary> {
  return apiGetJson(
    "/directory/personnel/import/normalized-records/summary",
    buildQuery({ batch_id: batchId })
  );
}

export async function listNormalizedRecords(
  params: {
    batch_id?: number;
    employee_id?: number;
    review_status?: NormalizedRecordReviewStatus;
    record_kind?: NormalizedRecordKind;
    q_name?: string;
    q_iin?: string;
    binding_status?: "bound" | "unbound" | "conflict";
    hide_unchanged?: boolean;
    limit?: number;
    offset?: number;
  } = {}
): Promise<{
  total: number;
  limit: number;
  offset: number;
  items: NormalizedRecord[];
  skipped?: boolean;
  hide_unchanged?: boolean;
}> {
  return apiGetJson("/directory/personnel/import/normalized-records", buildQuery(params));
}

export async function getNormalizedRecord(recordId: number): Promise<NormalizedRecord> {
  return apiGetJson(`/directory/personnel/import/normalized-records/${recordId}`);
}

export async function patchNormalizedRecordEmployeeBinding(
  recordId: number,
  employeeId: number
): Promise<NormalizedRecord> {
  return apiPatchJson(`/directory/personnel/import/normalized-records/${recordId}`, {
    employee_id: employeeId,
  });
}

export type EnrollEmployeeConflict = {
  code: "IIN_ALREADY_EXISTS" | "IIN_MULTIPLE_MATCH";
  existing_employee_id?: number;
  existing_employee_name?: string;
  existing_org_unit_name?: string;
  existing_position_name?: string;
  candidate_employee_ids?: number[];
  candidates?: Array<{
    employee_id: number;
    full_name?: string;
    org_unit_name?: string;
    position_name?: string;
  }>;
  message?: string;
};

export type EnrollEmployeeResponse = {
  dry_run: boolean;
  outcome: "ready" | "created" | "conflict" | "blocked";
  created: boolean;
  matched_by: string;
  employee_id?: number | null;
  linked_records_count: number;
  linked_record_ids: number[];
  linked_row_ids: number[];
  warnings: string[];
  preview: {
    full_name: string;
    iin: string;
    org_unit_id?: number | null;
    org_unit_name?: string;
    position_id?: number | null;
    position_name?: string;
    date_from?: string;
    employment_rate?: number;
    org_unit_hint?: {
      value?: string;
      org_unit_id?: number | null;
      org_unit_name?: string;
      source?: string;
      confidence?: string;
    } | null;
    position_hint?: { value?: string; source?: string } | null;
    record_kind?: string;
    source_sheet?: string;
    source_row_number?: number | null;
  };
  provenance: {
    origin_type?: string;
    source_batch_id?: number;
    source_batch_file_name?: string;
    source_row_id?: number;
    source_normalized_record_id?: number;
    trigger_record_kind?: string;
    source_field?: string;
    created_by_user_id?: number;
  };
  conflict?: EnrollEmployeeConflict | null;
};

export class EnrollEmployeeConflictError extends Error {
  payload: EnrollEmployeeResponse;

  constructor(payload: EnrollEmployeeResponse) {
    super(payload.conflict?.message || "Конфликт при enrollment");
    this.name = "EnrollEmployeeConflictError";
    this.payload = payload;
  }
}

export type EnrollEmployeeRequestBody = {
  dry_run?: boolean;
  full_name?: string;
  org_unit_id?: number;
  position_id?: number;
  date_from?: string;
  employment_rate?: number;
  link_same_iin_in_batch?: boolean;
};

export async function enrollEmployeeFromNormalizedRecord(
  recordId: number,
  body: EnrollEmployeeRequestBody = {}
): Promise<EnrollEmployeeResponse> {
  const url = resolveApiUrl(
    `/directory/personnel/import/normalized-records/${recordId}/enroll-employee`
  );
  const res = await fetch(url, {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (res.status === 409) {
    const raw = (await res.json().catch(() => ({}))) as { detail?: EnrollEmployeeResponse };
    const payload = raw.detail ?? (raw as EnrollEmployeeResponse);
    throw new EnrollEmployeeConflictError(payload);
  }
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw parseErrorBody(res.status, text, "Не удалось выполнить enrollment.");
  }
  return res.json() as Promise<EnrollEmployeeResponse>;
}

export type RepairBatchEmployeeBindingsResult = {
  batch_id: number;
  rows_processed: number;
  bound: number;
  already_bound: number;
  unbound: number;
  conflict: number;
  normalized_records_updated: number;
};

export async function repairBatchEmployeeBindings(
  batchId: number
): Promise<RepairBatchEmployeeBindingsResult> {
  return apiPostJson(`/directory/personnel/import/batches/${batchId}/employee-bindings/repair`, {});
}

export type RosterPromotionOutcome =
  | "would_create"
  | "would_update"
  | "already_linked"
  | "exists"
  | "conflict"
  | "blocked";

export type RosterPromotionItem = {
  row_id: number;
  outcome: RosterPromotionOutcome;
  full_name: string;
  iin: string;
  employee_id?: number | null;
  target_employee_id?: number | null;
  org_unit_id?: number | null;
  org_unit_name?: string;
  position_id?: number | null;
  position_name?: string;
  needs_hr_review?: boolean;
  reason?: string | null;
  candidate_employee_ids?: number[];
};

export type RosterPromotionResponse = {
  batch_id: number;
  dry_run: boolean;
  total_rows: number;
  summary: Record<RosterPromotionOutcome, number>;
  items: RosterPromotionItem[];
  applied?: RosterPromotionItem[];
  binding_repair?: Record<string, unknown>;
};

export async function promoteImportRosterBatch(
  batchId: number,
  body: { dry_run?: boolean; row_ids?: number[] } = {}
): Promise<RosterPromotionResponse> {
  return apiPostJson(`/directory/personnel/import/batches/${batchId}/roster-promotion`, body);
}

export async function patchNormalizedRecordReview(
  recordId: number,
  body: { review_status: NormalizedRecordReviewStatus; review_notes?: string }
): Promise<NormalizedRecord> {
  return apiPatchJson(`/directory/personnel/import/normalized-records/${recordId}`, body);
}

export async function patchNormalizedRecordReviewOverride(
  recordId: number,
  reviewOverride: NormalizedRecordReviewOverride
): Promise<NormalizedRecord> {
  return apiPatchJson(`/directory/personnel/import/normalized-records/${recordId}`, {
    review_override: reviewOverride,
  });
}

export type {
  PromotionBlockerCode,
} from "./normalizedRecordPromotionLabels";

export {
  PROMOTION_BLOCKER_CODES,
  PROMOTION_BLOCKER_LABELS,
  PROMOTION_BLOCKER_PANEL_GROUPS,
  PROMOTION_SKIP_REASON_LABELS,
  getPromotionBlockerLabel,
  sumBlockersByCodes,
} from "./normalizedRecordPromotionLabels";

export type PromotionBlocker = {
  code: string;
  message: string;
  field?: string;
};

export type PromotionPreview = {
  document_type_code?: string | null;
  medical_specialty_id?: number | null;
  title?: string | null;
  training_title?: string | null;
  issued_by?: string | null;
  issued_at?: string | null;
  end_date?: string | null;
  valid_until?: string | null;
  hours?: number | null;
  document_number?: string | null;
  file_url?: string | null;
  source_record_key?: string | null;
};

export type PromotionItemResult = {
  record_id: number;
  normalized_record_id: number;
  record_kind: string;
  employee_id: number | null;
  outcome: string;
  document_id?: number;
  reason?: string;
  blockers?: PromotionBlocker[];
  preview?: PromotionPreview;
};

export type PromotionResponse = {
  dry_run: boolean;
  requested: number;
  promoted: number;
  would_promote: number;
  skipped: number;
  would_skip: number;
  failed: number;
  would_fail: number;
  items: PromotionItemResult[];
  summary_by_blocker: Record<string, number>;
  skipped_unavailable?: boolean;
};

export type PromoteNormalizedRecordsRequest = {
  record_ids?: number[];
  batch_id?: number;
  filters?: {
    employee_id?: number;
    record_kind?: string;
    review_status?: string;
  };
  dry_run?: boolean;
  stop_on_first_error?: boolean;
};

export async function promoteNormalizedRecords(
  body: PromoteNormalizedRecordsRequest
): Promise<PromotionResponse> {
  return apiPostJson("/directory/personnel/import/normalized-records/promote", body);
}

export const NORMALIZED_REVIEW_STATUS_LABELS: Record<NormalizedRecordReviewStatus, string> = {
  pending: "Ожидает проверки",
  approved: "Утверждено",
  rejected: "Отклонено",
  promoted: "Промотировано",
  superseded: "Заменено",
};

export const SHEET_TYPE_LABELS: Record<string, string> = {
  doctors: "Врачи",
  nurses: "Медсестра / СМР",
  junior_staff: "Младший персонал",
  other_staff: "Прочие",
  part_time: "Совместители",
  declaration: "Декларации",
};

export type CanonicalSnapshotExportParams = {
  source_type?: string;
  snapshot_id?: number;
  include_metadata?: boolean;
};

export function buildCanonicalSnapshotExportUrl(
  params: CanonicalSnapshotExportParams = {},
): string {
  const q = buildQuery({
    source_type: params.source_type ?? "roster",
    snapshot_id: params.snapshot_id,
    include_metadata: params.include_metadata,
  });
  return resolveApiUrl(
    `/directory/personnel/canonical-snapshot/export.xlsx${q ? `?${q}` : ""}`,
  );
}

export async function downloadCanonicalSnapshotExport(
  params: CanonicalSnapshotExportParams = {},
): Promise<void> {
  const url = buildCanonicalSnapshotExportUrl(params);
  const res = await fetch(url, { method: "GET", headers: authHeaders(), cache: "no-store" });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw parseErrorBody(res.status, body, "Не удалось выгрузить эталонный Excel.");
  }
  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename=\"?([^\";]+)\"?/i);
  const filename = match?.[1] || "canonical_snapshot.xlsx";
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}
