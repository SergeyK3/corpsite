import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import NormalizedRecordsSummaryPanel from "./NormalizedRecordsSummaryPanel";

const { getNormalizedRecordsSummary } = vi.hoisted(() => ({
  getNormalizedRecordsSummary: vi.fn(),
}));

vi.mock("../_lib/importApi.client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../_lib/importApi.client")>();
  return {
    ...actual,
    getNormalizedRecordsSummary,
  };
});

describe("NormalizedRecordsSummaryPanel", () => {
  afterEach(() => cleanup());

  beforeEach(() => {
    vi.clearAllMocks();
    getNormalizedRecordsSummary.mockResolvedValue({
      total: 42,
      pending: 10,
      approved: 20,
      rejected: 2,
      promoted: 8,
      superseded: 2,
      by_kind: {
        training: 12,
        certificate: 8,
        category: 14,
        education: 8,
      },
    });
  });

  it("loads and renders normalized records summary for batch", async () => {
    render(<NormalizedRecordsSummaryPanel batchId={809} />);

    await waitFor(() => expect(screen.getByTestId("normalized-summary-total")).toHaveTextContent("42"));
    expect(getNormalizedRecordsSummary).toHaveBeenCalledWith(809);
    expect(screen.getByTestId("normalized-summary-pending")).toHaveTextContent("10");
    expect(screen.getByTestId("normalized-summary-approved")).toHaveTextContent("20");
    expect(screen.getByTestId("normalized-summary-rejected")).toHaveTextContent("2");
    expect(screen.getByTestId("normalized-summary-promoted")).toHaveTextContent("8");
    expect(screen.getByTestId("normalized-summary-kind-training")).toHaveTextContent("12");
    expect(screen.getByTestId("normalized-summary-kind-certificate")).toHaveTextContent("8");
    expect(screen.getByTestId("normalized-summary-kind-category")).toHaveTextContent("14");
    expect(screen.getByTestId("normalized-summary-kind-education")).toHaveTextContent("8");
  });
});
