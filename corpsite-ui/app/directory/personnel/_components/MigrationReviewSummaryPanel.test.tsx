import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import MigrationReviewSummaryPanel from "./MigrationReviewSummaryPanel";
import type { NormalizedRecord } from "../_lib/importApi.client";

const record: NormalizedRecord = {
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

describe("MigrationReviewSummaryPanel", () => {
  afterEach(() => {
    cleanup();
  });

  it("shows readiness badge when commit is allowed", () => {
    render(
      <MigrationReviewSummaryPanel
        employee={{ id: "45", fio: "Иванов Иван", department: null, position: null, org_unit: null, rate: null, status: "active", date_from: null, date_to: null }}
        domain={{
          domain_code: "education",
          display_name: "Образование",
          description: null,
          is_enabled: true,
          target_table_names: [],
          control_list_columns: [],
          created_at: null,
          updated_at: null,
        }}
        source="review"
        record={record}
        isDraft
        hasPersonLink
      />,
    );

    expect(screen.getByText("Готово к переносу")).toBeInTheDocument();
    expect(screen.getByText("ПК · КазНМУ")).toBeInTheDocument();
  });
});
