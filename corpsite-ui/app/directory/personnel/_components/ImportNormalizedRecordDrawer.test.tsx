import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ImportNormalizedRecordDrawer from "./ImportNormalizedRecordDrawer";
import type { NormalizedRecord } from "../_lib/importApi.client";

const fullIin = "851101300451";

const sampleRecord: NormalizedRecord = {
  record_id: 42,
  normalized_record_id: 42,
  batch_id: 7,
  row_id: 11,
  employee_id: null,
  employee_binding: {
    status: "unbound",
    method: null,
    reason: "Сотрудник с указанным ИИН не найден в справочнике",
    employee_id: null,
    directory_employee_name: null,
    candidate_employee_ids: [],
  },
  full_name: "Иванов Иван",
  iin: fullIin,
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
  review_status: "pending",
  reviewed_at: null,
  reviewed_by: null,
  review_notes: null,
  promoted_document_id: null,
  promoted_at: null,
  promoted_by: null,
  created_at: "2026-06-01T10:00:00.000Z",
  updated_at: "2026-06-01T10:00:00.000Z",
};

describe("ImportNormalizedRecordDrawer", () => {
  it("renders full IIN without masking", () => {
    render(
      <ImportNormalizedRecordDrawer
        record={sampleRecord}
        open
        onClose={vi.fn()}
        onReviewed={vi.fn()}
        onToast={vi.fn()}
      />
    );

    expect(screen.getByText(fullIin)).toBeInTheDocument();
    expect(screen.queryByText(/8511\*+/)).not.toBeInTheDocument();
  });
});
