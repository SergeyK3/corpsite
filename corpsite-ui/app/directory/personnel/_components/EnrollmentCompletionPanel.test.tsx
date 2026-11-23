import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import EnrollmentCompletionPanel, {
  buildImportCardAccountHref,
} from "./EnrollmentCompletionPanel";
import { OPEN_HR_DOSSIER_CTA } from "@/lib/personnelCardTerminology";
import type { EnrollEmployeeResponse, NormalizedRecord } from "../_lib/importApi.client";

vi.mock("../../employees/_components/EmployeeAccountSections", () => ({
  default: ({
    employeeId,
    showEvents,
    showTelegram,
  }: {
    employeeId: string;
    showEvents?: boolean;
    showTelegram?: boolean;
  }) => (
    <div data-testid="employee-account-sections">
      account-section:{employeeId}:events={String(showEvents)}:telegram={String(showTelegram)}
    </div>
  ),
}));

const baseRecord: NormalizedRecord = {
  record_id: 42,
  normalized_record_id: 42,
  batch_id: 7,
  row_id: 11,
  employee_id: 100,
  employee_binding: {
    status: "bound",
    method: "manual",
    reason: null,
    employee_id: 100,
    directory_employee_name: "Иванов Иван",
    candidate_employee_ids: [],
  },
  full_name: "Иванов Иван",
  iin: "851101300451",
  fragment_index: 0,
  source_field: "training_raw",
  source_text: "ПК",
  source_record_key: "training:0",
  record_kind: "training",
  document_type_id: null,
  document_type_code: null,
  title: "ПК",
  provider: null,
  hours: null,
  start_date: null,
  end_date: null,
  issue_date: null,
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

const enrollResult: EnrollEmployeeResponse = {
  dry_run: false,
  outcome: "created",
  created: true,
  matched_by: "iin",
  employee_id: 100,
  linked_records_count: 2,
  linked_record_ids: [42, 43],
  linked_row_ids: [11, 12],
  warnings: [],
  preview: {
    full_name: "Иванов Иван",
    iin: "851101300451",
  },
  provenance: {},
};

describe("EnrollmentCompletionPanel", () => {
  afterEach(() => {
    cleanup();
  });

  it("shows lifecycle completion checklist and embeds account provisioning UI", () => {
    render(
      <EnrollmentCompletionPanel
        employeeId={100}
        enrollResult={enrollResult}
        record={baseRecord}
        batchFileName="june.csv"
      />
    );

    expect(screen.getByText(/✓ Сотрудник создан · ID 100/)).toBeInTheDocument();
    expect(screen.getByText("Сотрудник добавлен в персонал")).toBeInTheDocument();
    expect(screen.getByText(/Привязка HR-записей \(2\)/)).toBeInTheDocument();
    expect(screen.getByText("Контакт сотрудника")).toBeInTheDocument();
    expect(screen.getByText("Следующий шаг")).toBeInTheDocument();
    expect(screen.getByText(/Учётная запись Corpsite создаётся отдельно/)).toBeInTheDocument();
    expect(screen.getByTestId("employee-account-sections")).toHaveTextContent(
      "account-section:100:events=false:telegram=false"
    );
  });

  it("links to employee card provisioning route", () => {
    render(
      <EnrollmentCompletionPanel
        employeeId={100}
        enrollResult={enrollResult}
        record={baseRecord}
      />
    );

    expect(buildImportCardAccountHref(100)).toBe(
      "/directory/personnel/employees/100/card?section=access&provisionAccount=1"
    );
    expect(screen.getByRole("link", { name: OPEN_HR_DOSSIER_CTA })).toHaveAttribute(
      "href",
      "/directory/personnel/employees/100/card?section=access&provisionAccount=1"
    );
  });
});
