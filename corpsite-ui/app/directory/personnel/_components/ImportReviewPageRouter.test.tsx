import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const mockSearchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useSearchParams: () => mockSearchParams,
}));

vi.mock("./ImportInitialBaselinePageClient", () => ({
  default: () => <div data-testid="import-initial-baseline-page" />,
}));

vi.mock("./ImportHrReviewPageClient", () => ({
  default: () => <div data-testid="import-hr-review-page" />,
}));

vi.mock("./PersonnelImportNormalizedRecordsReviewPageClient", () => ({
  default: ({ initialBatchId }: { initialBatchId?: number }) => (
    <div data-testid="import-normalized-records-review-page" data-initial-batch-id={initialBatchId ?? ""} />
  ),
}));

import ImportReviewPageRouter from "./ImportReviewPageRouter";

describe("ImportReviewPageRouter", () => {
  it("routes mode=initial to initial baseline page", () => {
    mockSearchParams.set("mode", "initial");
    mockSearchParams.delete("batch");

    render(<ImportReviewPageRouter />);

    expect(screen.getByTestId("import-initial-baseline-page")).toBeInTheDocument();
    expect(screen.queryByTestId("import-normalized-records-review-page")).not.toBeInTheDocument();
  });

  it("routes mode=hr to HR discrepancy review page", () => {
    mockSearchParams.set("mode", "hr");
    mockSearchParams.delete("batch");

    render(<ImportReviewPageRouter />);

    expect(screen.getByTestId("import-hr-review-page")).toBeInTheDocument();
  });

  it("routes default to normalized records review and passes batch query", () => {
    mockSearchParams.delete("mode");
    mockSearchParams.set("batch", "809");

    render(<ImportReviewPageRouter />);

    const page = screen.getByTestId("import-normalized-records-review-page");
    expect(page).toBeInTheDocument();
    expect(page).toHaveAttribute("data-initial-batch-id", "809");
  });
});
