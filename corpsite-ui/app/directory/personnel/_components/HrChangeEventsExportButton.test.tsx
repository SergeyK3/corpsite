import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import HrChangeEventsExportButton from "./HrChangeEventsExportButton";

vi.mock("../_lib/hrChangeEventsApi.client", () => ({
  downloadHrChangeEventsExport: vi.fn().mockResolvedValue(undefined),
  mapHrChangeEventsApiError: (e: unknown) => String(e),
}));

describe("HrChangeEventsExportButton", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders export button", () => {
    render(<HrChangeEventsExportButton />);
    expect(screen.getByTestId("hr-change-events-export-button")).toHaveTextContent(
      "Выгрузить изменения Excel",
    );
  });

  it("triggers download with current filters", async () => {
    const { downloadHrChangeEventsExport } = await import("../_lib/hrChangeEventsApi.client");
    render(
      <HrChangeEventsExportButton
        filters={{ event_type: "NEW", department: "Терапия", q: "Иванов" }}
      />,
    );
    fireEvent.click(screen.getByTestId("hr-change-events-export-button"));
    await waitFor(() => {
      expect(downloadHrChangeEventsExport).toHaveBeenCalledWith({
        event_type: "NEW",
        department: "Терапия",
        q: "Иванов",
      });
    });
  });
});
