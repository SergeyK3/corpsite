import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import PersonnelImportNormalizedRecordsReviewPageClient from "./PersonnelImportNormalizedRecordsReviewPageClient";
import { RESTORE_IMPORT_BATCH_BINDINGS_LABEL } from "./RestoreImportBatchBindingsPanel";

vi.mock("./ImportNormalizedRecordDrawer", () => ({
  default: () => null,
}));

vi.mock("./ImportMonthlyDiffSummaryPanel", () => ({
  default: () => null,
}));

vi.mock("./NormalizedRecordsPromotionPanel", () => ({
  default: () => null,
}));

vi.mock("../_lib/importApi.client", () => ({
  EMPLOYEE_BINDING_STATUS_LABELS: {
    bound: "Привязан",
    unbound: "Не привязан",
    conflict: "Конфликт",
  },
  employeeBindingBadgeClass: () => "",
  getNormalizedRecord: vi.fn(),
  getNormalizedRecordsSummary: vi.fn().mockResolvedValue({
    total: 0,
    pending: 0,
    approved: 0,
    rejected: 0,
    promoted: 0,
    superseded: 0,
    by_kind: { training: 0, certificate: 0, category: 0, education: 0 },
    skipped: false,
  }),
  listImportBatches: vi.fn().mockResolvedValue({ items: [] }),
  listNormalizedRecords: vi.fn().mockResolvedValue({ total: 0, items: [], limit: 50, offset: 0 }),
  mapImportApiError: (error: unknown) => String(error),
  NORMALIZED_RECORD_KIND_LABELS: {},
  NORMALIZED_RECORD_KINDS: [],
  NORMALIZED_RECORD_KIND_SUMMARY_LABELS: {},
  NORMALIZED_REVIEW_STATUS_LABELS: {},
  repairBatchEmployeeBindings: vi.fn(),
}));

describe("PersonnelImportNormalizedRecordsReviewPageClient restore bindings UX", () => {
  it("does not render restore bindings button without selected batch", async () => {
    render(<PersonnelImportNormalizedRecordsReviewPageClient />);

    expect(screen.queryByTestId("restore-import-batch-bindings-button")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: RESTORE_IMPORT_BATCH_BINDINGS_LABEL })).not.toBeInTheDocument();
  });

  it("renders restore bindings button when batch is pre-selected", async () => {
    render(<PersonnelImportNormalizedRecordsReviewPageClient initialBatchId={77} />);

    expect(await screen.findByTestId("restore-import-batch-bindings-button")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: RESTORE_IMPORT_BATCH_BINDINGS_LABEL })).toBeInTheDocument();
    expect(screen.getByTestId("restore-import-batch-bindings-button")).toHaveAttribute("data-batch-id", "77");
  });
});
