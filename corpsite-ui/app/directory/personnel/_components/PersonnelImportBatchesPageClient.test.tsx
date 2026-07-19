import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PersonnelImportBatchesPageClient from "./PersonnelImportBatchesPageClient";

const {
  deleteImportBatch,
  listImportBatches,
  listInitialBaselineSourceSelections,
  setInitialBaselineSourceSelection,
} = vi.hoisted(() => ({
  deleteImportBatch: vi.fn(),
  listImportBatches: vi.fn(),
  listInitialBaselineSourceSelections: vi.fn(),
  setInitialBaselineSourceSelection: vi.fn(),
}));

vi.mock("./CanonicalSnapshotExportButton", () => ({
  default: () => null,
}));

vi.mock("./PersonnelBaselinesJournalSection", () => ({
  default: () => <div data-testid="personnel-baselines-journal-mock" />,
}));

vi.mock("../_lib/importApi.client", () => ({
  deleteImportBatch,
  listImportBatches,
  listInitialBaselineSourceSelections,
  setInitialBaselineSourceSelection,
  mapImportApiError: (error: unknown) => String(error),
}));

const JUNE_BATCHES = [
  {
    batch_id: 801,
    import_code: "2606-01",
    can_delete: false,
    file_name: "контрольный2606-a.xlsx",
    original_filename: "контрольный2606-a.xlsx",
    report_period: "06.2026",
    report_month: "2026-06-01",
    source_last_modified_at: "2026-06-15T10:00:00Z",
    status: "APPLY_PENDING",
    total_rows: 100,
    error_rows: 0,
    imported_at: "2026-06-16T12:00:00Z",
  },
  {
    batch_id: 802,
    import_code: "2606-02",
    can_delete: false,
    file_name: "контрольный2606-b.xlsx",
    original_filename: "контрольный2606-b.xlsx",
    report_period: "06.2026",
    report_month: "2026-06-01",
    source_last_modified_at: "2026-06-17T10:00:00Z",
    status: "APPLY_PENDING",
    total_rows: 110,
    error_rows: 0,
    imported_at: "2026-06-18T12:00:00Z",
  },
];

describe("PersonnelImportBatchesPageClient batch actions", () => {
  afterEach(() => cleanup());

  it("renders import code column and open/continue links for each batch row", async () => {
    listImportBatches.mockResolvedValue({ items: [JUNE_BATCHES[0]] });
    listInitialBaselineSourceSelections.mockResolvedValue({ items: [] });

    render(<PersonnelImportBatchesPageClient />);

    expect(await screen.findByTestId("import-batch-number-801")).toHaveTextContent("2606-01");
    expect(screen.getByTestId("import-batch-number-801")).toHaveAttribute(
      "href",
      "/directory/personnel/import/801",
    );
    expect(screen.getByText("контрольный2606-a.xlsx")).toBeInTheDocument();
    expect(screen.getByText("06.2026")).toBeInTheDocument();
    expect(screen.getByText("Проверка завершена")).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Аналитика" })).toHaveAttribute(
      "href",
      "/directory/personnel/import/801",
    );
    expect(screen.getByRole("link", { name: "Review" })).toHaveAttribute(
      "href",
      "/directory/personnel/import/801/review",
    );
    expect(screen.getByRole("link", { name: "Обучение" })).toHaveAttribute(
      "href",
      "/directory/personnel/import/801/training",
    );
    expect(screen.getByTestId("personnel-baselines-journal-mock")).toBeInTheDocument();
  });

  it("switches selected baseline source between 2606-01 and 2606-02", async () => {
    listImportBatches.mockResolvedValue({ items: JUNE_BATCHES });
    listInitialBaselineSourceSelections.mockResolvedValue({ items: [] });
    setInitialBaselineSourceSelection.mockImplementation(async (body: { source_batch_id: number }) => ({
      report_period: "2026-06-01",
      source_batch_id: body.source_batch_id,
      import_code: body.source_batch_id === 801 ? "2606-01" : "2606-02",
      lifecycle_status: "ACTIVE",
      mutable: true,
    }));

    render(<PersonnelImportBatchesPageClient />);

    expect(await screen.findByTestId("initial-baseline-select-801")).toBeInTheDocument();
    expect(screen.getByTestId("initial-baseline-select-802")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("initial-baseline-select-801"));
    await waitFor(() => {
      expect(setInitialBaselineSourceSelection).toHaveBeenCalledWith({
        report_period: "2026-06-01",
        source_batch_id: 801,
      });
    });
    await waitFor(() => {
      expect(screen.getByTestId("initial-baseline-selected-801")).toHaveTextContent("✓ Выбран");
    });
    expect(screen.queryByTestId("initial-baseline-selected-802")).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId("initial-baseline-select-802"));
    await waitFor(() => {
      expect(setInitialBaselineSourceSelection).toHaveBeenLastCalledWith({
        report_period: "2026-06-01",
        source_batch_id: 802,
      });
    });
    await waitFor(() => {
      expect(screen.getByTestId("initial-baseline-selected-802")).toHaveTextContent("✓ Выбран");
    });
    expect(screen.queryByTestId("initial-baseline-selected-801")).not.toBeInTheDocument();
  });
});
