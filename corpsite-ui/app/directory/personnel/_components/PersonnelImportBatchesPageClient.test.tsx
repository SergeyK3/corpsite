import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import PersonnelImportBatchesPageClient from "./PersonnelImportBatchesPageClient";

vi.mock("./CanonicalSnapshotExportButton", () => ({
  default: () => null,
}));

vi.mock("../_lib/importApi.client", () => ({
  deleteImportBatch: vi.fn(),
  listImportBatches: vi.fn().mockResolvedValue({
    items: [
      {
        batch_id: 42,
        file_name: "control-list.xlsx",
        status: "staged",
        total_rows: 100,
        error_rows: 2,
        imported_at: "2026-06-16T12:00:00Z",
      },
    ],
  }),
  mapImportApiError: (error: unknown) => String(error),
}));

describe("PersonnelImportBatchesPageClient batch actions", () => {
  it("renders open/continue links for each batch row", async () => {
    render(<PersonnelImportBatchesPageClient />);

    expect(await screen.findByRole("link", { name: "Аналитика" })).toHaveAttribute(
      "href",
      "/directory/personnel/import/42"
    );
    expect(screen.getByRole("link", { name: "Review" })).toHaveAttribute(
      "href",
      "/directory/personnel/import/42/review"
    );
    expect(screen.getByRole("link", { name: "Документы" })).toHaveAttribute(
      "href",
      "/directory/personnel/import/42/training"
    );
    expect(screen.getByRole("button", { name: "Удалить" })).toBeInTheDocument();
  });
});
