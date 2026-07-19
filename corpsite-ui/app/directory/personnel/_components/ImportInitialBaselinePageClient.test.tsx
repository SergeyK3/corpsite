import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ImportInitialBaselinePageClient from "./ImportInitialBaselinePageClient";
import PersonnelBaselinesJournalSection from "./PersonnelBaselinesJournalSection";

const {
  listImportBatches,
  getInitialBaselineSourceSelection,
  getImportSummary,
  getSheetDiagnostics,
  getNormalizedRecordsSummary,
  listStagingRows,
  getRowReviewDetail,
  getDepartmentRecodingOptions,
  listMonthlyReferenceForkSources,
  listControlListBaselines,
  apiAuthMe,
} = vi.hoisted(() => ({
  listImportBatches: vi.fn(),
  getInitialBaselineSourceSelection: vi.fn(),
  getImportSummary: vi.fn(),
  getSheetDiagnostics: vi.fn(),
  getNormalizedRecordsSummary: vi.fn(),
  listStagingRows: vi.fn(),
  getRowReviewDetail: vi.fn(),
  getDepartmentRecodingOptions: vi.fn(),
  listMonthlyReferenceForkSources: vi.fn(),
  listControlListBaselines: vi.fn(),
  apiAuthMe: vi.fn(),
}));

vi.mock("@/lib/api", () => ({ apiAuthMe }));
vi.mock("@/lib/personnelNav", () => ({ canSeeHrProcessesNav: () => true }));
vi.mock("@/lib/adminNav", () => ({ isPrivilegedOperator: () => false }));

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams("report_period=2026-06-01&mode=initial"),
}));

vi.mock("../_lib/importApi.client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../_lib/importApi.client")>();
  return {
    ...actual,
    listImportBatches,
    getInitialBaselineSourceSelection,
    getImportSummary,
    getSheetDiagnostics,
    getNormalizedRecordsSummary,
    listStagingRows,
    getRowReviewDetail,
    getDepartmentRecodingOptions,
    listControlListBaselines,
  };
});

vi.mock("../_lib/mrdApi.client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../_lib/mrdApi.client")>();
  return {
    ...actual,
    listMonthlyReferenceForkSources,
  };
});

const SAMPLE_BATCH = {
  batch_id: 809,
  import_code: "IMP-809",
  file_name: "june-control-list.xlsx",
  imported_at: "2026-06-20T10:00:00Z",
  status: "APPLY_PENDING",
  report_period: "2026-06-01",
  total_rows: 120,
  valid_rows: 118,
  error_rows: 0,
};

const SAMPLE_ROW = {
  row_id: 501,
  full_name: "Иванова А.А.",
  iin: "850101300123",
  birth_date: "1985-01-01",
  age: 41,
  department: "Терапия",
  org_unit_id: 10,
  org_unit_name: "Терапия",
  position_raw: "Медсестра",
  training_raw: "Курсы 2025",
  certification_raw: "2 категория",
  education_raw: "Колледж",
  source_sheet: "медсестры",
  source_row_number: 12,
  sheet_type: "nurses",
  classification: "employee",
};

describe("ImportInitialBaselinePageClient", () => {
  afterEach(() => cleanup());

  beforeEach(() => {
    vi.clearAllMocks();
    apiAuthMe.mockResolvedValue({ user_id: 1, roles: ["personnel_admin"] });
    getDepartmentRecodingOptions.mockResolvedValue({ groups: [], departments: [] });
    listImportBatches.mockResolvedValue({ items: [SAMPLE_BATCH] });
    getInitialBaselineSourceSelection.mockResolvedValue({ item: null });
    getImportSummary.mockResolvedValue({
      batch_id: 809,
      total_rows: 120,
      valid_rows: 118,
      error_rows: 0,
      valid_iin: 118,
      by_sheet_type: {},
      with_training: 10,
      with_certification: 10,
      missing_full_name: 0,
      missing_iin: 0,
      invalid_iin: 0,
      duplicate_iin_groups: 0,
      duplicate_iin_rows: 0,
    });
    getSheetDiagnostics.mockResolvedValue({
      batch_id: 809,
      items: [],
      totals: { rows_total: 120, employee_rows: 100, declaration_rows: 10, technical_rows: 10, candidates_count: 50 },
    });
    getNormalizedRecordsSummary.mockResolvedValue({
      total: 42,
      pending: 10,
      approved: 20,
      rejected: 2,
      promoted: 8,
      superseded: 2,
      by_kind: { training: 12, certificate: 8, category: 14, education: 8 },
    });
    listStagingRows.mockImplementation((_batchId: number, params?: { limit?: number }) => {
      const payload = { total: 1, items: [SAMPLE_ROW], offset: 0 };
      if (params?.limit === 500) {
        return Promise.resolve({ ...payload, limit: 500 });
      }
      return Promise.resolve({ ...payload, limit: 200 });
    });
    getRowReviewDetail.mockResolvedValue({
      batch_id: 809,
      row_id: 501,
      employee_id: null,
      full_name: "Иванова А.А.",
      iin: "850101300123",
      birth_date: "1985-01-01",
      sex: "F",
      employment_rate: 1,
      department: "Терапия",
      department_source: "import",
      department_recoding: { org_unit_id: 10, org_unit_name: "Терапия", department_group: "CLINICAL" },
      position_raw: "Медсестра",
      staff_type: "nurses",
      is_part_time: false,
      sheet_type: "nurses",
      classification: "employee",
      declaration_group: "",
      profile: { full_name: "Иванова А.А.", iin: "850101300123" },
      education: [],
      experience_raw: "",
      training: [],
      qualification_categories: [],
      certificates: [],
      degrees: { candidate_medical_sciences: false, doctor_medical_sciences: false, raw_text: "" },
      awards: [],
      notes: [],
      ai_extraction: null,
      source_sheet: "медсестры",
      source_row_number: 12,
    });
  });

  it("loads initial mode with existing import pipeline data", async () => {
    render(<ImportInitialBaselinePageClient />);
    await waitFor(() => expect(screen.getByTestId("import-initial-baseline-page")).toBeInTheDocument());
    expect(screen.getByTestId("initial-baseline-import-picker")).toHaveValue("809");
    await waitFor(() => expect(screen.getByTestId("normalized-records-summary")).toBeInTheDocument());
    expect(getNormalizedRecordsSummary).toHaveBeenCalledWith(809);
    await waitFor(() => expect(screen.getByTestId("import-data-issue-summary")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByTestId("summary-total-rows")).toHaveTextContent("120"));
    expect(screen.getByTestId("summary-rows-without-errors")).toHaveTextContent("118");
    expect(screen.getByTestId("summary-rows-with-errors")).toHaveTextContent("0");
    expect(listStagingRows).toHaveBeenCalledWith(
      809,
      expect.objectContaining({ roster_scope: "personnel", hide_unchanged: false, limit: 500 }),
    );
  });

  it("opens manual fields for ambiguous values", async () => {
    render(<ImportInitialBaselinePageClient />);
    await waitFor(() => expect(screen.getByText("Иванова А.А.")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("initial-fix-data-501"));
    await waitFor(() => expect(getRowReviewDetail).toHaveBeenCalledWith(809, 501));
    expect(screen.getAllByText("Контрольный файл").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Нормализованное значение").length).toBeGreaterThan(0);
    expect(screen.getByTestId("initial-manual-501-education_raw")).toBeInTheDocument();
    expect(screen.getByTestId("initial-baseline-create-action")).toBeDisabled();
  });

  it("links to normalized review when no completed imports are available", async () => {
    listImportBatches.mockResolvedValue({
      items: [{ ...SAMPLE_BATCH, status: "IN_REVIEW" }],
    });

    render(<ImportInitialBaselinePageClient />);

    await waitFor(() => expect(screen.getByTestId("initial-baseline-complete-review-link")).toBeInTheDocument());
    expect(screen.getByTestId("initial-baseline-complete-review-link")).toHaveAttribute(
      "href",
      "/directory/personnel/import/review?batch=809",
    );
  });
});

describe("PersonnelBaselinesJournalSection period buttons", () => {
  afterEach(() => cleanup());

  beforeEach(() => {
    vi.clearAllMocks();
    apiAuthMe.mockResolvedValue({ user_id: 1, roles: ["personnel_admin"] });
    listControlListBaselines.mockResolvedValue({ items: [] });
    listMonthlyReferenceForkSources.mockResolvedValue({
      items: [
        {
          mrd_id: 7,
          report_period: "2026-07-01",
          version: 1,
          status: "ACTIVE",
          row_version: 1,
          entry_count: 12,
          forked_from_reference_id: null,
          is_active_for_period: true,
        },
      ],
      active_by_period: { "2026-07-01": 7 },
    });
  });

  it("shows June form-baseline button linking to mode=initial", async () => {
    vi.setSystemTime(new Date(2026, 6, 19));
    render(<PersonnelBaselinesJournalSection embedded />);
    await waitFor(() => expect(screen.getByTestId("mrd-journal-table")).toBeInTheDocument());
    const link = screen.getByTestId("journal-form-initial-2026-06");
    expect(link).toHaveTextContent("Сформировать эталон");
    expect(link).toHaveAttribute("href", "/directory/personnel/import/review?report_period=2026-06-01&mode=initial");
    vi.useRealTimers();
  });

  it("routes July action to June initial formation while June MRD is missing", async () => {
    vi.setSystemTime(new Date(2026, 6, 19));
    render(<PersonnelBaselinesJournalSection embedded />);
    await waitFor(() => expect(screen.getByTestId("journal-july-blocked-until-june")).toBeInTheDocument());
    expect(screen.getByTestId("journal-july-blocked-until-june")).toHaveAttribute(
      "href",
      "/directory/personnel/import/review?report_period=2026-06-01&mode=initial&blocked_period=2026-07-01",
    );
    vi.useRealTimers();
  });
});
