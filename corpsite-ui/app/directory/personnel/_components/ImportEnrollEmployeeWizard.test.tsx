import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ImportEnrollEmployeeWizard, {
  isValidOptionalIsoDate,
} from "./ImportEnrollEmployeeWizard";
import { getOrgUnitsTree } from "@/app/directory/org-units/_lib/api.client";
import { loadOrgUnitSelectOptions } from "@/lib/orgUnitsSelect";
import { loadScopedPositionOptions, loadGlobalPositionCatalogCached } from "@/lib/taskOrgFilters";
import {
  enrollEmployeeFromNormalizedRecord,
  getNormalizedRecord,
  type EnrollEmployeeResponse,
  type NormalizedRecord,
} from "../_lib/importApi.client";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/directory/personnel/import",
  useSearchParams: () => new URLSearchParams(""),
}));

vi.mock("@/lib/orgScope", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/orgScope")>();
  return {
    ...actual,
    fetchDepartmentGroups: vi.fn(async () => [
      { group_id: 1, group_name: "Клинические" },
      { group_id: 2, group_name: "Параклинические" },
      { group_id: 3, group_name: "Административно-хозяйственные" },
    ]),
  };
});

vi.mock("@/app/directory/org-units/_lib/api.client", () => ({
  getOrgUnitsTree: vi.fn(),
}));

vi.mock("@/lib/orgUnitsSelect", () => ({
  loadOrgUnitSelectOptions: vi.fn(),
}));

vi.mock("@/lib/taskOrgFilters", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/taskOrgFilters")>();
  return {
    ...actual,
    loadScopedPositionOptions: vi.fn(),
    loadGlobalPositionCatalogCached: vi.fn(),
  };
});

vi.mock("../_lib/importApi.client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../_lib/importApi.client")>();
  return {
    ...actual,
    enrollEmployeeFromNormalizedRecord: vi.fn(),
    getNormalizedRecord: vi.fn(),
  };
});

const CLINICAL_GROUP_ID = 1;
const ADMIN_GROUP_ID = 3;

const orgUnitCatalog = [
  { unit_id: 42, name: "Стационар 1", group_id: CLINICAL_GROUP_ID },
  { unit_id: 44, name: "Амбулатория", group_id: CLINICAL_GROUP_ID },
  { unit_id: 73, name: "Отдел кадров", group_id: ADMIN_GROUP_ID },
];

const globalCatalog = [
  { id: 10, label: "Директор" },
  { id: 77, label: "Заместитель директора по менеджменту качества медицинской помощи" },
  { id: 99, label: "Заместитель директора по административным вопросам" },
  { id: 501, label: "Врач-терапевт" },
];

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

const dryRunReady: EnrollEmployeeResponse = {
  dry_run: true,
  outcome: "ready",
  created: false,
  matched_by: "iin",
  linked_records_count: 1,
  linked_record_ids: [42],
  linked_row_ids: [11],
  warnings: [],
  preview: {
    full_name: "Иванов Иван",
    iin: fullIin,
    position_hint: {
      value: "Заместитель директора по экономическим вопросам 04.05.2010г.",
      source: "import",
    },
  },
  provenance: {},
};

const IMPORT_POSITION_NOT_IN_CATALOG_WARNING =
  "Должность из импорта не найдена в справочнике должностей. Создайте должность в справочнике или выберите корректную существующую должность вручную.";

function renderWizard(dryRun: EnrollEmployeeResponse = dryRunReady) {
  vi.mocked(enrollEmployeeFromNormalizedRecord).mockResolvedValue(dryRun);
  render(
    <ImportEnrollEmployeeWizard
      record={baseRecord}
      canEnroll
      onReviewed={vi.fn()}
      onToast={vi.fn()}
    />,
  );
}

async function waitForWizardReady() {
  await waitFor(() => {
    expect(screen.getByTestId("enroll-wizard-main")).toBeInTheDocument();
    expect(screen.getByTestId("enroll-wizard-org-placement")).toBeInTheDocument();
  });
}

async function selectOrgGroup(groupId: string) {
  const groupSelect = await screen.findByTestId("org-scope-filter-select");
  await waitFor(() => {
    expect(groupSelect).not.toBeDisabled();
  });
  fireEvent.change(groupSelect, { target: { value: groupId } });
}

async function fillValidPlacement() {
  await selectOrgGroup(String(CLINICAL_GROUP_ID));

  const unitSelect = await screen.findByTestId("org-unit-scope-filter-select");
  fireEvent.change(unitSelect, { target: { value: "44" } });

  await waitFor(() => {
    expect(screen.getByTestId("enroll-wizard-position-select")).not.toBeDisabled();
  });

  fireEvent.change(screen.getByTestId("enroll-wizard-position-select"), {
    target: { value: "501" },
  });
}

async function openConfirmModal() {
  fireEvent.click(screen.getByTestId("enroll-wizard-confirm-checkbox"));
  fireEvent.click(screen.getByTestId("enroll-wizard-submit"));
  await waitFor(() => {
    expect(screen.getByTestId("enroll-wizard-confirm-modal")).toBeInTheDocument();
  });
}

describe("ImportEnrollEmployeeWizard single-screen UX", () => {
  beforeEach(() => {
    vi.mocked(loadOrgUnitSelectOptions).mockResolvedValue(orgUnitCatalog);
    vi.mocked(loadGlobalPositionCatalogCached).mockResolvedValue(globalCatalog);
    vi.mocked(loadScopedPositionOptions).mockImplementation(async (scope) => {
      if (scope.org_unit_id === 44) {
        return [{ id: 501, label: "Врач-терапевт" }];
      }
      if (scope.org_unit_id === 42) {
        return [{ id: 99, label: "Заместитель директора по административным вопросам" }];
      }
      return [];
    });
    vi.mocked(getOrgUnitsTree).mockResolvedValue({
      items: [
        { unit_id: 44, name: "Амбулатория", group_id: CLINICAL_GROUP_ID, children: [] },
        { unit_id: 73, name: "Отдел кадров", group_id: ADMIN_GROUP_ID, children: [] },
      ],
    } as Awaited<ReturnType<typeof getOrgUnitsTree>>);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("shows placement cascade immediately on open without extra navigation", async () => {
    renderWizard();
    await waitForWizardReady();

    expect(screen.getByTestId("org-scope-filter-select")).toBeInTheDocument();
    expect(screen.getByTestId("org-unit-scope-filter-select")).toBeInTheDocument();
    expect(screen.getByTestId("enroll-wizard-position-select")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Далее" })).not.toBeInTheDocument();
    expect(screen.queryByText("1. Источник")).not.toBeInTheDocument();
  });

  it("does not prefill admission date with current date", async () => {
    renderWizard();
    await waitForWizardReady();

    expect(screen.getByTestId("enroll-wizard-date-from")).toHaveValue("");
  });

  it("shows group → subdivision → position cascade behavior", async () => {
    renderWizard();
    await waitForWizardReady();
    await selectOrgGroup(String(CLINICAL_GROUP_ID));

    const unitSelect = await screen.findByTestId("org-unit-scope-filter-select");
    expect(unitSelect).not.toBeDisabled();
    expect(await screen.findByRole("option", { name: "Амбулатория" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Отдел кадров" })).not.toBeInTheDocument();

    fireEvent.change(unitSelect, { target: { value: "44" } });

    await waitFor(() => {
      expect(loadScopedPositionOptions).toHaveBeenCalledWith({
        org_group_id: CLINICAL_GROUP_ID,
        org_unit_id: 44,
        scope: "allowed",
      });
    });

    const positionSelect = screen.getByTestId("enroll-wizard-position-select");
    await waitFor(() => {
      expect(positionSelect).not.toBeDisabled();
    });
    expect(await screen.findByRole("option", { name: "Врач-терапевт" })).toBeInTheDocument();
  });

  it("blocks confirmation modal without org group", async () => {
    renderWizard();
    await waitForWizardReady();

    fireEvent.click(screen.getByTestId("enroll-wizard-confirm-checkbox"));
    fireEvent.click(screen.getByTestId("enroll-wizard-submit"));

    expect(await screen.findByTestId("enroll-wizard-error-org-group")).toHaveTextContent(
      "Выберите группу подразделений",
    );
    expect(screen.queryByTestId("enroll-wizard-confirm-modal")).not.toBeInTheDocument();
  });

  it("blocks confirmation modal without subdivision", async () => {
    renderWizard();
    await waitForWizardReady();
    await selectOrgGroup(String(CLINICAL_GROUP_ID));

    fireEvent.click(screen.getByTestId("enroll-wizard-confirm-checkbox"));
    fireEvent.click(screen.getByTestId("enroll-wizard-submit"));

    expect(await screen.findByTestId("enroll-wizard-error-org-unit")).toHaveTextContent(
      "Выберите подразделение",
    );
    expect(screen.queryByTestId("enroll-wizard-confirm-modal")).not.toBeInTheDocument();
  });

  it("blocks confirmation modal without position", async () => {
    renderWizard();
    await waitForWizardReady();
    await selectOrgGroup(String(CLINICAL_GROUP_ID));

    const unitSelect = await screen.findByTestId("org-unit-scope-filter-select");
    fireEvent.change(unitSelect, { target: { value: "44" } });
    await waitFor(() => {
      expect(screen.getByTestId("enroll-wizard-position-select")).not.toBeDisabled();
    });

    fireEvent.click(screen.getByTestId("enroll-wizard-confirm-checkbox"));
    fireEvent.click(screen.getByTestId("enroll-wizard-submit"));

    expect(await screen.findByTestId("enroll-wizard-error-position")).toHaveTextContent(
      "Выберите должность",
    );
    expect(screen.queryByTestId("enroll-wizard-confirm-modal")).not.toBeInTheDocument();
  });

  it("allows confirmation with empty admission date", async () => {
    renderWizard();
    await waitForWizardReady();
    await fillValidPlacement();
    await openConfirmModal();

    expect(screen.getByTestId("enroll-wizard-summary-date-from")).toHaveTextContent("Не указана");
  });

  it("omits date_from from payload when admission date is empty", async () => {
    const onReviewed = vi.fn();
    const onToast = vi.fn();
    const updatedRecord = { ...baseRecord, employee_id: 9001 };

    vi.mocked(enrollEmployeeFromNormalizedRecord)
      .mockResolvedValueOnce(dryRunReady)
      .mockResolvedValueOnce({
        dry_run: false,
        outcome: "created",
        created: true,
        employee_id: 9001,
        matched_by: "iin",
        linked_records_count: 1,
        linked_record_ids: [42],
        linked_row_ids: [11],
        warnings: [],
        preview: dryRunReady.preview,
        provenance: {},
      });
    vi.mocked(getNormalizedRecord).mockResolvedValue(updatedRecord);

    render(
      <ImportEnrollEmployeeWizard
        record={baseRecord}
        canEnroll
        onReviewed={onReviewed}
        onToast={onToast}
      />,
    );

    await waitForWizardReady();
    await fillValidPlacement();
    await openConfirmModal();

    fireEvent.click(screen.getByRole("button", { name: "Подтвердить и создать" }));

    await waitFor(() => {
      expect(enrollEmployeeFromNormalizedRecord).toHaveBeenLastCalledWith(42, {
        dry_run: false,
        full_name: "Иванов Иван",
        org_unit_id: 44,
        position_id: 501,
        employment_rate: 1,
        link_same_iin_in_batch: true,
      });
    });
    expect(enrollEmployeeFromNormalizedRecord).toHaveBeenLastCalledWith(
      42,
      expect.not.objectContaining({ date_from: expect.anything() }),
    );
    expect(onReviewed).toHaveBeenCalledWith(updatedRecord);
    expect(onToast).toHaveBeenCalledWith("Сотрудник создан и записи привязаны", "success");
  });

  it("sends date_from when user provides a valid admission date", async () => {
    vi.mocked(enrollEmployeeFromNormalizedRecord)
      .mockResolvedValueOnce(dryRunReady)
      .mockResolvedValueOnce({
        dry_run: false,
        outcome: "created",
        created: true,
        employee_id: 9001,
        matched_by: "iin",
        linked_records_count: 1,
        linked_record_ids: [42],
        linked_row_ids: [11],
        warnings: [],
        preview: dryRunReady.preview,
        provenance: {},
      });
    vi.mocked(getNormalizedRecord).mockResolvedValue({ ...baseRecord, employee_id: 9001 });

    renderWizard();
    await waitForWizardReady();
    await fillValidPlacement();

    fireEvent.change(screen.getByTestId("enroll-wizard-date-from"), {
      target: { value: "2024-03-15" },
    });

    await openConfirmModal();
    expect(screen.getByTestId("enroll-wizard-summary-date-from")).toHaveTextContent("15.03.2024");

    fireEvent.click(screen.getByRole("button", { name: "Подтвердить и создать" }));

    await waitFor(() => {
      expect(enrollEmployeeFromNormalizedRecord).toHaveBeenLastCalledWith(42, {
        dry_run: false,
        full_name: "Иванов Иван",
        org_unit_id: 44,
        position_id: 501,
        date_from: "2024-03-15",
        employment_rate: 1,
        link_same_iin_in_batch: true,
      });
    });
  });

  it("rejects invalid optional admission date values", () => {
    expect(isValidOptionalIsoDate("")).toBe(true);
    expect(isValidOptionalIsoDate("2024-03-15")).toBe(true);
    expect(isValidOptionalIsoDate("2024-02-30")).toBe(false);
    expect(isValidOptionalIsoDate("2024-13-01")).toBe(false);
  });

  it("clears subdivision and position when group changes", async () => {
    renderWizard();
    await waitForWizardReady();
    await fillValidPlacement();

    await selectOrgGroup(String(ADMIN_GROUP_ID));

    await waitFor(() => {
      expect(screen.getByTestId("org-unit-scope-filter-select")).toHaveValue("");
      expect(screen.getByTestId("enroll-wizard-position-select")).toHaveValue("");
    });
    expect(await screen.findByRole("option", { name: "Отдел кадров" })).toBeInTheDocument();
  });

  it("clears position when subdivision changes", async () => {
    renderWizard();
    await waitForWizardReady();
    await selectOrgGroup(String(CLINICAL_GROUP_ID));

    const unitSelect = await screen.findByTestId("org-unit-scope-filter-select");
    fireEvent.change(unitSelect, { target: { value: "44" } });
    await waitFor(() => {
      expect(screen.getByTestId("enroll-wizard-position-select")).not.toBeDisabled();
    });
    fireEvent.change(screen.getByTestId("enroll-wizard-position-select"), {
      target: { value: "501" },
    });

    fireEvent.change(unitSelect, { target: { value: "42" } });

    await waitFor(() => {
      expect(screen.getByTestId("enroll-wizard-position-select")).toHaveValue("");
    });
  });

  it("prefills group and subdivision from org_unit_id hint", async () => {
    const dryRunWithUnitHint: EnrollEmployeeResponse = {
      ...dryRunReady,
      preview: {
        ...dryRunReady.preview,
        org_unit_hint: {
          org_unit_id: 44,
          value: "Амбулатория",
          source: "import",
        },
      },
    };

    renderWizard(dryRunWithUnitHint);
    await waitForWizardReady();

    await waitFor(() => {
      expect(screen.getByTestId("org-scope-filter-select")).toHaveValue(String(CLINICAL_GROUP_ID));
      expect(screen.getByTestId("org-unit-scope-filter-select")).toHaveValue("44");
    });
    expect(getOrgUnitsTree).toHaveBeenCalled();
  });

  it("prefills exact position match from import hint", async () => {
    const matchingDryRun: EnrollEmployeeResponse = {
      ...dryRunReady,
      preview: {
        ...dryRunReady.preview,
        org_unit_hint: {
          org_unit_id: 44,
          value: "Амбулатория",
          source: "import",
        },
        position_hint: {
          value: "Заместитель директора по менеджменту качества медицинской помощи",
          source: "import",
        },
      },
    };

    renderWizard(matchingDryRun);
    await waitForWizardReady();

    await waitFor(() => {
      expect(screen.getByTestId("org-unit-scope-filter-select")).toHaveValue("44");
    });

    await waitFor(() => {
      expect(screen.getByTestId("enroll-wizard-position-select")).toHaveValue("77");
    });

    expect(
      screen.getByText(
        "Совпадение с импортом: Заместитель директора по менеджменту качества медицинской помощи",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText(IMPORT_POSITION_NOT_IN_CATALOG_WARNING)).not.toBeInTheDocument();
  });

  it("shows confirmation modal with human-readable names", async () => {
    renderWizard();
    await waitForWizardReady();
    await fillValidPlacement();
    await openConfirmModal();

    expect(screen.getByTestId("enroll-wizard-summary-org-group")).toHaveTextContent("Клинические");
    expect(screen.getByTestId("enroll-wizard-summary-org-unit")).toHaveTextContent("Амбулатория");
    expect(screen.getByTestId("enroll-wizard-summary-position")).toHaveTextContent("Врач-терапевт");
    expect(screen.getByTestId("enroll-wizard-summary-linked-count")).toHaveTextContent(
      "1 (same batch + same IIN)",
    );
    expect(screen.queryByText(/отделение #/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/должность #/i)).not.toBeInTheDocument();
  });

  it("shows import position missing warning when hint does not match catalog", async () => {
    renderWizard();
    await waitForWizardReady();
    await selectOrgGroup(String(CLINICAL_GROUP_ID));

    const unitSelect = await screen.findByTestId("org-unit-scope-filter-select");
    fireEvent.change(unitSelect, { target: { value: "44" } });

    await waitFor(() => {
      expect(screen.getByText(IMPORT_POSITION_NOT_IN_CATALOG_WARNING)).toBeInTheDocument();
    });
  });
});
