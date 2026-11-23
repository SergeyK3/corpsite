import { describe, expect, it } from "vitest";

import type { NormalizedRecord } from "./importApi.client";
import {
  buildAddDraftItemPayloadFromNormalizedRecord,
  buildMigrationCandidateId,
  buildMigrationSessionHref,
  canShowMigrationCta,
  findNormalizedRecordByCandidateId,
  normalizedRecordToMigrationDomain,
  parseMigrationCandidateId,
} from "./personnelMigrationCandidates";

const baseRecord: NormalizedRecord = {
  record_id: 42,
  normalized_record_id: 42,
  batch_id: 7,
  row_id: 11,
  employee_id: 45,
  full_name: "Иванов Иван",
  iin: "851101300451",
  fragment_index: 0,
  source_field: "training_raw",
  source_text: "ПК 144 ч",
  source_record_key: "training:0",
  record_kind: "training",
  document_type_id: null,
  document_type_code: null,
  title: "ПК",
  provider: "КазНМУ",
  hours: 144,
  start_date: null,
  end_date: null,
  issue_date: "2020-01-01",
  expiry_date: null,
  document_number: null,
  specialty_text: null,
  medical_specialty_id: null,
  file_url: null,
  parse_method: "rule",
  confidence: 0.9,
  review_status: "approved",
  reviewed_at: null,
  reviewed_by: null,
  review_notes: null,
  promoted_document_id: null,
  promoted_at: null,
  promoted_by: null,
  created_at: "2026-06-01T10:00:00.000Z",
  updated_at: "2026-06-01T10:00:00.000Z",
};

describe("personnelMigrationCandidates", () => {
  it("builds and parses stable candidate_id", () => {
    const candidateId = buildMigrationCandidateId("education", 42);
    expect(candidateId).toBe("education:normalized_record:42");
    expect(parseMigrationCandidateId(candidateId)).toEqual({
      domainCode: "education",
      sourceKind: "normalized_record",
      sourceRecordId: 42,
    });
  });

  it("maps training record_kind to education domain", () => {
    expect(normalizedRecordToMigrationDomain("training")).toBe("education");
    expect(normalizedRecordToMigrationDomain("certificate")).toBeNull();
  });

  it("allows migration CTA only for approved bound records", () => {
    expect(canShowMigrationCta(baseRecord)).toBe(true);
    expect(canShowMigrationCta({ ...baseRecord, review_status: "pending" })).toBe(false);
    expect(canShowMigrationCta({ ...baseRecord, employee_id: null })).toBe(false);
  });

  it("builds review session href with query params", () => {
    const href = buildMigrationSessionHref({
      domainCode: "education",
      employeeId: 45,
      candidateId: "education:normalized_record:42",
      source: "review",
    });
    expect(href).toBe(
      "/directory/personnel/migration/education/45?candidate_id=education%3Anormalized_record%3A42&source=review",
    );
  });

  it("builds add-item payload from normalized record", () => {
    const payload = buildAddDraftItemPayloadFromNormalizedRecord(baseRecord);
    expect(payload.source_kind).toBe("normalized_record");
    expect(payload.source_record_id).toBe("42");
    expect(payload.record_kind).toBe("training");
    expect(payload.draft_payload).toMatchObject({
      training_kind: "continuing_education",
      title: "ПК",
    });
  });

  it("finds record by candidate_id", () => {
    const found = findNormalizedRecordByCandidateId(
      [baseRecord],
      "education:normalized_record:42",
    );
    expect(found?.normalized_record_id).toBe(42);
  });
});
