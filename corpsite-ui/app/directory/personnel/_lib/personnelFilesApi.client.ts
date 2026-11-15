import { apiFetchJson, buildHeaders, readJsonSafe, toApiError } from "@/lib/api";
import { resolveApiUrl } from "@/lib/apiBase";

export const fileKinds = { photo: "Фото лица", certificate: "Сертификат", diploma: "Диплом", identity: "Удостоверение личности", name_change: "Основание изменения ФИО" } as const;
export type FileKind = keyof typeof fileKinds;
export type NameProposal = { last_name: string; first_name: string; middle_name: string };
export type CertificateFacts = {
  document_id: number; certificate_entry_id: number | null; specialty_name_at_issue: string | null;
  specialty_code_at_issue: string | null; classifier_edition_at_issue: string | null;
  issued_at: string | null; valid_until: string | null; document_number: string | null;
  issued_by: string | null; lifecycle_status: string; verification_status: string | null;
};
export type CertificateInput = { employee_document_id: number } | {
  entry_id: number; specialty_name_at_issue: string; issued_at: string; valid_until: string;
  document_number?: string; issued_by?: string;
};
export type ClassifierEntry = { entry_id: number; edition_id: number; medical_specialty_id: number;
  specialty_code: string; specialty_name: string; edition_code: string; edition_title: string; accepts_new: boolean };
export type ClassifierCatalog = {
  can_manage: boolean;
  editions: { edition_id: number; code: string; title: string; source_reference: string; effective_from: string; accepts_new: boolean }[];
  entries: ClassifierEntry[];
  mappings: { mapping_id: number; from_entry_id: number; to_entry_id: number; source_reference: string; reason: string; effective_from: string; confirmed_by: number; confirmed_at: string; active: boolean }[];
  medical_specialties: { medical_specialty_id: number; name: string }[];
};
export type CertificateComparison = {
  previous: PersonnelFile | null; new_certificate: CertificateFacts | null;
  can_approve: boolean; context_token: string;
  basis: { kind: string; description: string; source_reference?: string; reason?: string;
    mapping_id?: number; confirmed_by?: number; confirmed_at?: string; effective_from?: string };
};
export type PersonnelFile = {
  version_id: string; set_id: string; person_id: number; kind: FileKind; title: string;
  version_no: number; state: "pending" | "returned" | "approved" | "superseded" | "revoked" | "archived";
  revision: number; original_name: string; mime_type: string; byte_size: number; page_count: number;
  reason: string; created_at: string; decided_at: string | null; proposed_name: NameProposal | null;
  name_applied_at: string | null; can_review: boolean; can_replace: boolean; can_export: boolean;
  full_name?: string;
  employee_document_id?: number | null; replaces_version_id?: string | null; certificate?: CertificateFacts | null;
};
export type FileList = { items: PersonnelFile[]; can_upload: boolean; can_review: boolean; can_history?: boolean; notifications?: FileEvent[] };
export type FileEvent = { event_id: number; version_id: string | null; actor_id: number; action: string; created_at: string; detail: Record<string, unknown> };
const base = "/api/personnel-files";
export const filesPath = (personId: number | null) => personId == null ? `${base}/me` : `${base}/persons/${personId}`;
export const listFiles = (personId: number | null) => apiFetchJson<FileList>(filesPath(personId));
export const fileHistory = (personId: number | null) => apiFetchJson<FileEvent[]>(`${filesPath(personId)}/history`);
export const reviewQueue = (after?: string) => apiFetchJson<{ items: PersonnelFile[]; next: string | null }>(`${base}/review-queue`, { query: { after } });
export const decideFile = (file: PersonnelFile, action: string, reason: string, comparison?: CertificateComparison | null) => apiFetchJson<PersonnelFile>(`${base}/versions/${file.version_id}/decision`, { method: "POST", body: { expected_revision: file.revision, action, reason, ...(comparison ? {expected_certificate_context: comparison.context_token} : {}) } });
export const applyFileName = (file: PersonnelFile, fullName: string, reason: string, effectiveDate: string) => apiFetchJson<PersonnelFile>(`${base}/versions/${file.version_id}/apply-name`, { method: "POST", body: { expected_revision: file.revision, expected_full_name: fullName, reason, effective_date: effectiveDate } });
export async function submitFile(personId: number | null, file: File, kind: FileKind, title: string, replacement?: PersonnelFile | null, proposal?: NameProposal, certificate?: CertificateInput) {
  const body = new FormData();
  body.append("file", file); body.append("kind", kind); body.append("title", title);
  if (replacement) { body.append("set_id", replacement.set_id); body.append("expected_revision", String(replacement.revision)); body.append("expected_version_id", replacement.version_id); }
  if (proposal) body.append("proposed_name", JSON.stringify(proposal));
  if (certificate) body.append("certificate", JSON.stringify(certificate));
  const res = await fetch(resolveApiUrl(filesPath(personId)), { method: "POST", headers: buildHeaders(), body, cache: "no-store" });
  const data = await readJsonSafe(res);
  if (!res.ok) throw toApiError(res.status, data);
  return data as PersonnelFile;
}
export async function fileBlob(file: PersonnelFile, operation: "preview" | "download" | "print", page = 1) {
  const res = await fetch(resolveApiUrl(`${base}/versions/${file.version_id}/${operation}?page=${page}`), { headers: buildHeaders(), cache: "no-store" });
  if (!res.ok) throw toApiError(res.status, await readJsonSafe(res));
  return res.blob();
}
export function fileError(error: unknown): string {
  return error && typeof error === "object" && "message" in error ? String(error.message) : "Не удалось выполнить операцию с файлом.";
}

export const acknowledgeFileNotifications = (through: number) => apiFetchJson(`${base}/me/notifications/read`, { method: "POST", body: { through_event_id: through } });
export const classifierCatalog = () => apiFetchJson<ClassifierCatalog>(`${base}/certificate-classifiers`);
export const registryCertificates = (personId: number | null) => apiFetchJson<{items: CertificateFacts[]}>(`${filesPath(personId)}/registry-certificates`);
export const certificateComparison = (file: PersonnelFile) => apiFetchJson<CertificateComparison>(`${base}/versions/${file.version_id}/review-context`);
export const manageClassifiers = (path: string, body: Record<string, unknown>) => apiFetchJson(`${base}/certificate-classifiers/${path}`, {method: "POST", body});
