import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ImportBatchContextHeader from "./ImportBatchContextHeader";

vi.mock("../_lib/importApi.client", () => ({
  getImportBatch: vi.fn().mockResolvedValue({
    batch_id: 148,
    file_name: "control-list.xlsx",
    imported_at: "2026-06-16T12:00:00Z",
    status: "staged",
    total_rows: 100,
    valid_rows: 98,
    error_rows: 2,
  }),
  mapImportApiError: (error: unknown) => String(error),
}));

describe("ImportBatchContextHeader", () => {
  it("shows import number, file name and uploaded at", async () => {
    render(<ImportBatchContextHeader batchId={148} />);

    expect(screen.getByText("Импорт 148")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText(/control-list\.xlsx/)).toBeInTheDocument();
    });
  });
});
