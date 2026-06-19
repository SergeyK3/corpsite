import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import CanonicalSnapshotExportButton from "./CanonicalSnapshotExportButton";

vi.mock("../_lib/importApi.client", () => ({
  downloadCanonicalSnapshotExport: vi.fn().mockResolvedValue(undefined),
  mapImportApiError: (e: unknown) => String(e),
}));

describe("CanonicalSnapshotExportButton", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders export button", () => {
    render(<CanonicalSnapshotExportButton />);
    expect(screen.getByTestId("canonical-snapshot-export-button")).toHaveTextContent(
      "Выгрузить эталонный Excel",
    );
  });

  it("triggers download on click", async () => {
    const { downloadCanonicalSnapshotExport } = await import("../_lib/importApi.client");
    render(<CanonicalSnapshotExportButton snapshotId={5} includeMetadata />);
    fireEvent.click(screen.getByTestId("canonical-snapshot-export-button"));
    await waitFor(() => {
      expect(downloadCanonicalSnapshotExport).toHaveBeenCalledWith({
        source_type: "roster",
        snapshot_id: 5,
        include_metadata: true,
      });
    });
  });
});
