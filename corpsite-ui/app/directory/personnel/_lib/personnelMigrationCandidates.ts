// PMF-4D — migration candidate helpers (frontend only).

import type { NormalizedRecord, NormalizedRecordKind } from "./importApi.client";
import type { AddMigrationDraftItemPayload } from "./personnelMigrationApi.client";

const CANDIDATE_ID_PATTERN = /^([^:]+):([^:]+):(\d+)$/;

export type ParsedMigrationCandidateId = {
  domainCode: string;
  sourceKind: string;
  sourceRecordId: number;
};

export function buildMigrationCandidateId(domainCode: string, normalizedRecordId: number): string {
  return `${domainCode}:normalized_record:${normalizedRecordId}`;
}

export function parseMigrationCandidateId(candidateId: string): ParsedMigrationCandidateId | null {
  const match = candidateId.trim().match(CANDIDATE_ID_PATTERN);
  if (!match) return null;
  const sourceRecordId = Number(match[3]);
  if (!Number.isFinite(sourceRecordId) || sourceRecordId <= 0) return null;
  return {
    domainCode: match[1],
    sourceKind: match[2],
    sourceRecordId,
  };
}

/** Map normalized record_kind to PMF domain_code (pilot: education only). */
export function normalizedRecordToMigrationDomain(recordKind: NormalizedRecordKind): string | null {
  if (recordKind === "education" || recordKind === "training") return "education";
  return null;
}

export function normalizedRecordKindsForDomain(domainCode: string): NormalizedRecordKind[] {
  if (domainCode === "education") return ["education", "training"];
  return [];
}

export function canShowMigrationCta(record: NormalizedRecord): boolean {
  if (record.review_status !== "approved") return false;
  if (!record.employee_id) return false;
  return normalizedRecordToMigrationDomain(record.record_kind) !== null;
}

export function buildMigrationSessionHref(args: {
  domainCode: string;
  employeeId: number;
  candidateId: string;
  source?: "review";
}): string {
  const params = new URLSearchParams({
    candidate_id: args.candidateId,
    source: args.source ?? "review",
  });
  return `/directory/personnel/migration/${encodeURIComponent(args.domainCode)}/${args.employeeId}?${params}`;
}

export function migrationCandidateSummary(record: NormalizedRecord): string {
  const parts: string[] = [];
  if (record.title?.trim()) parts.push(record.title.trim());
  if (record.provider?.trim()) parts.push(record.provider.trim());
  if (record.document_number?.trim()) parts.push(`№ ${record.document_number.trim()}`);
  if (parts.length > 0) return parts.join(" · ");
  if (record.source_text?.trim()) {
    const text = record.source_text.trim();
    return text.length > 80 ? `${text.slice(0, 77)}…` : text;
  }
  return `Запись #${record.normalized_record_id}`;
}

export function buildDraftPayloadFromNormalizedRecord(
  record: NormalizedRecord,
): Record<string, unknown> {
  const base = {
    source_field: record.source_field,
    source_text: record.source_text,
    parse_method: record.parse_method,
    confidence: record.confidence,
  };

  if (record.record_kind === "education") {
    return {
      ...base,
      education_kind: "other",
      institution_name: record.provider ?? record.title,
      specialty: record.specialty_text,
      diploma_number: record.document_number,
      document_date: record.issue_date,
      completed_at: record.issue_date ?? record.end_date,
    };
  }

  if (record.record_kind === "training") {
    return {
      ...base,
      training_kind: "continuing_education",
      title: record.title,
      organization_name: record.provider,
      hours: record.hours,
      document_date: record.issue_date,
      completed_at: record.end_date ?? record.issue_date,
      certificate_number: record.document_number,
    };
  }

  return base;
}

export function buildSourcePayloadFromNormalizedRecord(
  record: NormalizedRecord,
): Record<string, unknown> {
  return {
    normalized_record_id: record.normalized_record_id,
    record_id: record.record_id,
    batch_id: record.batch_id,
    row_id: record.row_id,
    record_kind: record.record_kind,
    review_status: record.review_status,
    full_name: record.full_name,
    iin: record.iin,
    title: record.title,
    provider: record.provider,
    source_record_key: record.source_record_key,
  };
}

export function buildAddDraftItemPayloadFromNormalizedRecord(
  record: NormalizedRecord,
): AddMigrationDraftItemPayload {
  return {
    source_kind: "normalized_record",
    source_record_id: String(record.normalized_record_id),
    import_batch_id: record.batch_id,
    import_row_id: record.row_id,
    record_kind: record.record_kind,
    draft_payload: buildDraftPayloadFromNormalizedRecord(record),
    source_payload: buildSourcePayloadFromNormalizedRecord(record),
  };
}

export function findNormalizedRecordByCandidateId(
  records: NormalizedRecord[],
  candidateId: string | null,
): NormalizedRecord | null {
  if (!candidateId) return null;
  const parsed = parseMigrationCandidateId(candidateId);
  if (!parsed || parsed.sourceKind !== "normalized_record") return null;
  return (
    records.find((row) => row.normalized_record_id === parsed.sourceRecordId) ?? null
  );
}
