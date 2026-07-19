import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ImportReviewProgressStrip from "./ImportReviewProgressStrip";

const assessImportReviewProgress = vi.fn();

vi.mock("../_lib/importApi.client", () => ({
  assessImportReviewProgress: (...args: unknown[]) => assessImportReviewProgress(...args),
  mapImportApiError: (error: unknown) => String(error),
}));

describe("ImportReviewProgressStrip", () => {
  afterEach(() => {
    cleanup();
    assessImportReviewProgress.mockReset();
  });

  beforeEach(() => {
    assessImportReviewProgress.mockResolvedValue({
      import_code: "2606-02",
      batch_id: 809,
      batch_status: "IN_REVIEW",
      already_completed: false,
      complete_allowed: false,
      blockers: [],
      review_progress: {
        pending_normalized: 0,
        error_rows: 0,
        pending_removals: 0,
        ready: true,
      },
    });
  });

  it("renders review metrics when assessment loads", async () => {
    render(
      <ImportReviewProgressStrip batchId={809} importCode="2606-02" batchStatus="IN_REVIEW" />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("review-progress-pending-normalized")).toHaveTextContent("0");
    });
    expect(screen.getByTestId("review-progress-error-rows")).toBeInTheDocument();
    expect(screen.getByTestId("review-progress-pending-removals")).toBeInTheDocument();
    expect(screen.getByTestId("review-progress-ready")).toHaveTextContent("Готов к эталону");
  });

  it("shows blocker summary while review queues remain", async () => {
    assessImportReviewProgress.mockResolvedValue({
      import_code: "2606-02",
      batch_id: 809,
      batch_status: "IN_REVIEW",
      already_completed: false,
      complete_allowed: false,
      blockers: [
        {
          code: "PENDING_NORMALIZED",
          message: "1975 pending",
          batch_id: 809,
          resolve_kind: "normalized_review",
          count: 1975,
        },
        {
          code: "PENDING_REMOVED_DECISIONS",
          message: "3 removals",
          batch_id: 809,
          resolve_kind: "removed_review",
          count: 3,
        },
      ],
      review_progress: {
        pending_normalized: 1975,
        error_rows: 233,
        pending_removals: 3,
        ready: false,
      },
    });

    render(
      <ImportReviewProgressStrip batchId={809} importCode="2606-02" batchStatus="IN_REVIEW" />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("review-progress-blockers")).toHaveTextContent(
        "Импорт ожидает проверки: не проверено 1975 записей, ошибок парсинга — 233, без решения «отсутствует в файле» — 3.",
      );
    });
    expect(screen.getByTestId("review-progress-ready")).toHaveTextContent("Ожидает проверки");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("shows auto-complete note when batch is already review-completed", async () => {
    assessImportReviewProgress.mockResolvedValue({
      import_code: "2606-02",
      batch_id: 809,
      batch_status: "APPLY_PENDING",
      already_completed: true,
      complete_allowed: true,
      blockers: [],
      review_progress: {
        pending_normalized: 0,
        error_rows: 0,
        pending_removals: 0,
        ready: true,
      },
    });

    render(
      <ImportReviewProgressStrip batchId={809} importCode="2606-02" batchStatus="IN_REVIEW" />,
    );

    await waitFor(() => {
      expect(screen.getByText(/все очереди обработаны, переход выполнен автоматически/i)).toBeInTheDocument();
    });
  });
});
