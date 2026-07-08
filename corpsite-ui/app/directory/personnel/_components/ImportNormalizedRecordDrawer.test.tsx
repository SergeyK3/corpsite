import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ImportEnrollEmployeeWizard from "./ImportEnrollEmployeeWizard";
import ImportNormalizedRecordDrawer from "./ImportNormalizedRecordDrawer";
import type { NormalizedRecord } from "../_lib/importApi.client";

vi.mock("./ImportEnrollEmployeeWizard", () => ({
  default: ({ canEnroll }: { canEnroll?: boolean }) =>
    canEnroll ? <div data-testid="enroll-wizard">Добавить в персонал</div> : null,
}));

const fullIin = "851101300451";

const baseRecord: NormalizedRecord = {
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

function renderDrawer(
  record: NormalizedRecord,
  options: { canEnrollEmployee?: boolean; canProvisionAccount?: boolean } = {},
) {
  const { canEnrollEmployee = true, canProvisionAccount = true } = options;
  render(
    <ImportNormalizedRecordDrawer
      record={record}
      open
      canEnrollEmployee={canEnrollEmployee}
      canProvisionAccount={canProvisionAccount}
      onClose={vi.fn()}
      onReviewed={vi.fn()}
      onToast={vi.fn()}
    />
  );
}

const boundRecord: NormalizedRecord = {
  ...baseRecord,
  employee_id: 45,
  employee_binding: {
    status: "bound",
    method: "enroll",
    reason: null,
    employee_id: 45,
    directory_employee_name: "Козгамбаева Ляззат Таласпаевна",
    candidate_employee_ids: [],
  },
};

const approvedBoundRecord: NormalizedRecord = {
  ...boundRecord,
  review_status: "approved",
};

describe("ImportNormalizedRecordDrawer", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders full IIN without masking", () => {
    renderDrawer(baseRecord);

    expect(screen.getByText(fullIin)).toBeInTheDocument();
    expect(screen.queryByText(/8511\*+/)).not.toBeInTheDocument();
  });

  it("does not render masked IIN from legacy b483232 API payloads", () => {
    renderDrawer({
      ...baseRecord,
      iin: "8511****51",
    });

    expect(screen.queryByText(/8511\*+/)).not.toBeInTheDocument();
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("does not render iin_masked even when present on the object", () => {
    const legacyRecord = {
      ...baseRecord,
      iin: "",
      iin_masked: "8511****51",
    } as NormalizedRecord & { iin_masked?: string };

    renderDrawer(legacyRecord);

    expect(screen.queryByText(/8511\*+/)).not.toBeInTheDocument();
  });

  it("shows enroll wizard for unlinked record when HR can enroll", () => {
    renderDrawer(baseRecord, { canEnrollEmployee: true });
    expect(screen.getByTestId("enroll-wizard")).toBeInTheDocument();
  });

  it("hides enroll wizard when canEnrollEmployee is false", () => {
    renderDrawer(baseRecord, { canEnrollEmployee: false });
    expect(screen.queryByTestId("enroll-wizard")).not.toBeInTheDocument();
  });

  it("shows bound record provisioning CTA with import-card link", () => {
    renderDrawer(boundRecord, { canProvisionAccount: true });

    expect(
      screen.getByText(
        "Сотрудник уже создан в персонале. Если сотруднику нужен вход в систему, выдайте доступ к Corpsite."
      )
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Открыть карту импорта и доступ" })).toHaveAttribute(
      "href",
      "/directory/personnel/employees/45/import-card?provisionAccount=1"
    );
    expect(screen.getByRole("link", { name: "Открыть в «Персонале»" })).toHaveAttribute(
      "href",
      "/directory/staff?employeeId=45"
    );
    expect(screen.queryByTestId("enroll-wizard")).not.toBeInTheDocument();
  });

  it("hides bound record provisioning CTA for unbound records", () => {
    renderDrawer(baseRecord, { canProvisionAccount: true });

    expect(screen.queryByRole("link", { name: "Открыть карту импорта и доступ" })).not.toBeInTheDocument();
  });

  it("hides bound record provisioning CTA when provisioning is not allowed", () => {
    renderDrawer(boundRecord, { canProvisionAccount: false });

    expect(screen.queryByRole("link", { name: "Открыть карту импорта и доступ" })).not.toBeInTheDocument();
    expect(
      screen.queryByText(
        "Сотрудник уже создан в персонале. Если сотруднику нужен вход в систему, выдайте доступ к Corpsite."
      )
    ).not.toBeInTheDocument();
  });

  it("shows migration CTA for approved bound education/training records", () => {
    renderDrawer(approvedBoundRecord);

    const link = screen.getByRole("link", { name: "Перенести в кадровую карточку" });
    expect(link).toHaveAttribute(
      "href",
      "/directory/personnel/migration/education/45?candidate_id=education%3Anormalized_record%3A42&source=review",
    );
  });

  it("hides migration CTA for pending records", () => {
    renderDrawer(baseRecord);
    expect(screen.queryByRole("link", { name: "Перенести в кадровую карточку" })).not.toBeInTheDocument();
  });
});
