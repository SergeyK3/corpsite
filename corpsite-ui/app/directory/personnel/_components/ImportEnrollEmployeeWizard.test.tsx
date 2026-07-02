import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ImportEnrollEmployeeWizard from "./ImportEnrollEmployeeWizard";
import { getPositions } from "@/app/directory/employees/_lib/api.client";
import { getOrgUnitsTree } from "@/app/directory/org-units/_lib/api.client";
import {
  enrollEmployeeFromNormalizedRecord,
  type EnrollEmployeeResponse,
  type NormalizedRecord,
} from "../_lib/importApi.client";

vi.mock("@/app/directory/employees/_lib/api.client", () => ({
  getPositions: vi.fn(),
}));

vi.mock("@/app/directory/org-units/_lib/api.client", () => ({
  getOrgUnitsTree: vi.fn(),
}));

vi.mock("../_lib/importApi.client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../_lib/importApi.client")>();
  return {
    ...actual,
    enrollEmployeeFromNormalizedRecord: vi.fn(),
  };
});

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

const globalCatalog = {
  items: [
    { position_id: 10, name: "Директор" },
    { position_id: 11, name: "Заместитель директора" },
    { position_id: 20, name: "Бухгалтер" },
    {
      position_id: 77,
      name: "Заместитель директора по менеджменту качества медицинской помощи",
    },
    { position_id: 99, name: "Заместитель директора по административным вопросам" },
  ],
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
    />
  );
}

async function openStepTwo() {
  await waitFor(() => {
    expect(screen.getByRole("button", { name: "Далее" })).not.toBeDisabled();
  });
  fireEvent.click(screen.getByRole("button", { name: "Далее" }));
  await waitFor(() => {
    expect(screen.getByText("Отделение *")).toBeInTheDocument();
  });
}

function orgUnitSelect(): HTMLSelectElement {
  return screen.getByRole("combobox", { name: /Отделение/i }) as HTMLSelectElement;
}

function positionSelect(): HTMLSelectElement {
  return screen.getAllByRole("combobox")[1] as HTMLSelectElement;
}

describe("ImportEnrollEmployeeWizard position filtering", () => {
  beforeEach(() => {
    vi.mocked(getOrgUnitsTree).mockResolvedValue({
      items: [
        { unit_id: 1, name: "Администрация", children: [] },
        { unit_id: 2, name: "Бухгалтерия", children: [] },
      ],
    } as Awaited<ReturnType<typeof getOrgUnitsTree>>);
    vi.mocked(getPositions).mockImplementation(async (args) => {
      if (args?.org_unit_id === 1) {
        return {
          items: [{ position_id: 99, name: "Заместитель директора по административным вопросам" }],
        };
      }
      if (args?.org_unit_id === 2) {
        return { items: [{ position_id: 20, name: "Бухгалтер" }] };
      }
      return globalCatalog;
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("does not load positions until an org unit is selected", async () => {
    renderWizard();
    await openStepTwo();

    expect(getPositions).not.toHaveBeenCalled();
    expect(positionSelect()).toBeDisabled();
    expect(screen.getByRole("option", { name: "Сначала выберите отделение" })).toBeInTheDocument();
  });

  it("loads global catalog even when scoped positions contain only one unrelated position", async () => {
    renderWizard();
    await openStepTwo();

    fireEvent.change(orgUnitSelect(), { target: { value: "1" } });

    await waitFor(() => {
      expect(getPositions).toHaveBeenCalledWith({ limit: 500 });
      expect(getPositions).toHaveBeenCalledWith({ org_unit_id: 1, limit: 500 });
    });

    await waitFor(() => {
      expect(positionSelect()).not.toBeDisabled();
    });

    expect(screen.getByRole("option", { name: "Директор" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Бухгалтер" })).toBeInTheDocument();
    expect(
      screen.getByRole("option", {
        name: "Заместитель директора по менеджменту качества медицинской помощи",
      })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("option", { name: "Заместитель директора по административным вопросам" })
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Используются в отделении: Заместитель директора по административным вопросам"
      )
    ).toBeInTheDocument();
    expect(
      screen.getByText("Из импорта: Заместитель директора по экономическим вопросам 04.05.2010г.")
    ).toBeInTheDocument();
    expect(positionSelect().value).toBe("");
    expect(screen.getByText(IMPORT_POSITION_NOT_IN_CATALOG_WARNING)).toBeInTheDocument();
  });

  it("does not auto-select unrelated scoped position", async () => {
    renderWizard();
    await openStepTwo();

    fireEvent.change(orgUnitSelect(), { target: { value: "1" } });

    await waitFor(() => {
      expect(positionSelect()).not.toBeDisabled();
    });

    expect(positionSelect().value).toBe("");
    expect(positionSelect().value).not.toBe("99");
  });

  it("shows warning when import position is missing from catalog", async () => {
    renderWizard();
    await openStepTwo();

    fireEvent.change(orgUnitSelect(), { target: { value: "1" } });

    await waitFor(() => {
      expect(screen.getByText(IMPORT_POSITION_NOT_IN_CATALOG_WARNING)).toBeInTheDocument();
    });
  });

  it("prefills exact import match and hides missing-catalog warning", async () => {
    const matchingDryRun: EnrollEmployeeResponse = {
      ...dryRunReady,
      preview: {
        ...dryRunReady.preview,
        position_hint: {
          value: "Заместитель директора по менеджменту качества медицинской помощи",
          source: "import",
        },
      },
    };

    renderWizard(matchingDryRun);
    await openStepTwo();

    fireEvent.change(orgUnitSelect(), { target: { value: "1" } });

    await waitFor(() => {
      expect(positionSelect().value).toBe("77");
    });

    expect(
      screen.getByText(
        "Совпадение с импортом: Заместитель директора по менеджменту качества медицинской помощи"
      )
    ).toBeInTheDocument();
    expect(screen.queryByText(IMPORT_POSITION_NOT_IN_CATALOG_WARNING)).not.toBeInTheDocument();
    expect(
      screen.getByText(
        "Из импорта: Заместитель директора по менеджменту качества медицинской помощи"
      )
    ).toBeInTheDocument();
  });

  it("clears position and shows validation when org unit changes", async () => {
    renderWizard();
    await openStepTwo();

    fireEvent.change(orgUnitSelect(), { target: { value: "1" } });
    await waitFor(() => expect(positionSelect()).not.toBeDisabled());
    fireEvent.change(positionSelect(), { target: { value: "10" } });
    expect(positionSelect().value).toBe("10");

    fireEvent.change(orgUnitSelect(), { target: { value: "2" } });

    await waitFor(() => {
      expect(getPositions).toHaveBeenCalledWith({ org_unit_id: 2, limit: 500 });
    });
    await waitFor(() => {
      expect(positionSelect().value).toBe("");
    });
    expect(
      screen.getByText("Выбранная должность сброшена — выберите должность для нового отделения")
    ).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Директор" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Бухгалтер" })).toBeInTheDocument();
  });

  it("shows blocked placeholder when global catalog is empty", async () => {
    vi.mocked(getPositions).mockResolvedValue({ items: [] });

    renderWizard();
    await openStepTwo();

    fireEvent.change(orgUnitSelect(), { target: { value: "1" } });

    await waitFor(() => {
      expect(getPositions).toHaveBeenCalledWith({ limit: 500 });
      expect(getPositions).toHaveBeenCalledWith({ org_unit_id: 1, limit: 500 });
    });
    await waitFor(() => {
      expect(screen.getByRole("option", { name: "Нет доступных должностей" })).toBeInTheDocument();
    });
    expect(positionSelect()).toBeDisabled();
  });
});
