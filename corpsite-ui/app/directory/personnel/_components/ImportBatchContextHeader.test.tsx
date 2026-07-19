import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ImportBatchContextHeader from "./ImportBatchContextHeader";

vi.mock("../_lib/importApi.client", () => {
  const mockBatch = {
    batch_id: 148,
    import_code: "2606-02",
    file_name: "контрольный2606.xlsx",
    original_filename: "контрольный2606.xlsx",
    technical_filename: "control-list-2606-02.xlsx",
    report_period: "06.2026",
    imported_at: "2026-06-16T12:00:00Z",
    status: "IN_REVIEW",
    total_rows: 100,
    valid_rows: 98,
    error_rows: 2,
    byte_size: 12345,
  };

  return {
    getImportBatch: vi.fn().mockResolvedValue(mockBatch),
    listImportBatches: vi.fn().mockResolvedValue({
      items: [
        mockBatch,
        {
          batch_id: 147,
          import_code: "2606-01",
          file_name: "контрольный2605.xlsx",
          original_filename: "контрольный2605.xlsx",
          report_period: "05.2026",
          imported_at: "2026-05-16T12:00:00Z",
          status: "IN_REVIEW",
          total_rows: 90,
          valid_rows: 88,
          error_rows: 2,
        },
      ],
    }),
    mapImportApiError: (error: unknown) => String(error),
  };
});

describe("ImportBatchContextHeader", () => {
  it("shows import code, file name and uploaded at", async () => {
    render(<ImportBatchContextHeader batchId={148} />);

    await waitFor(() => {
      expect(screen.getByText("Импорт 2606-02")).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByText(/контрольный2606\.xlsx/)).toBeInTheDocument();
      expect(screen.getByText(/control-list-2606-02\.xlsx/)).toBeInTheDocument();
    });
  });

  it("renders selectable dropdown and calls onBatchChange", async () => {
    const onBatchChange = vi.fn();
    render(<ImportBatchContextHeader batchId={148} selectable onBatchChange={onBatchChange} />);

    await waitFor(() => {
      expect(screen.getByTestId("import-batch-selector")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("import-batch-selector"), { target: { value: "147" } });
    expect(onBatchChange).toHaveBeenCalledWith(147);
  });
});
