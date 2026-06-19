import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import NormalizedRecordsPromotionPanel from "./NormalizedRecordsPromotionPanel";
import { PROMOTE_DISABLED_MESSAGES } from "../_lib/normalizedRecordPromotionUx";

const promoteNormalizedRecords = vi.fn();

vi.mock("../_lib/importApi.client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../_lib/importApi.client")>();
  return {
    ...actual,
    promoteNormalizedRecords: (...args: unknown[]) => promoteNormalizedRecords(...args),
  };
});

describe("NormalizedRecordsPromotionPanel disabled-state UX", () => {
  beforeEach(() => {
    promoteNormalizedRecords.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it("shows NO_BATCH reason when batch is not selected", () => {
    render(
      <NormalizedRecordsPromotionPanel
        batchId=""
        recordKind=""
        tableUnavailable={false}
        onCompleted={vi.fn()}
        onToast={vi.fn()}
      />,
    );

    expect(screen.getByTestId("promote-disabled-reason")).toHaveTextContent(
      PROMOTE_DISABLED_MESSAGES.NO_BATCH,
    );
    expect(screen.getByRole("button", { name: "Promote" })).toBeDisabled();
  });

  it("shows DRY_RUN_REQUIRED when batch has approved records but dry-run was not run", () => {
    render(
      <NormalizedRecordsPromotionPanel
        batchId="39"
        recordKind=""
        tableUnavailable={false}
        approvedInBatch={3}
        pendingInBatch={3477}
        normalizedInBatch={3500}
        onCompleted={vi.fn()}
        onToast={vi.fn()}
      />,
    );

    expect(screen.getByTestId("promotion-scope-label")).toHaveTextContent("Promotion scope: Batch #39");
    expect(screen.getByTestId("promotion-pending-note")).toHaveTextContent(
      "Pending records: 3 477. Они не участвуют в promotion и не блокируют его.",
    );
    expect(screen.getByTestId("promote-disabled-reason")).toHaveTextContent(
      PROMOTE_DISABLED_MESSAGES.DRY_RUN_REQUIRED,
    );
  });

  it("shows NO_READY_RECORDS when batch has zero approved records", () => {
    render(
      <NormalizedRecordsPromotionPanel
        batchId="39"
        recordKind=""
        tableUnavailable={false}
        approvedInBatch={0}
        pendingInBatch={100}
        normalizedInBatch={25}
        onCompleted={vi.fn()}
        onToast={vi.fn()}
      />,
    );

    expect(screen.getByTestId("promote-disabled-reason")).toHaveTextContent(
      PROMOTE_DISABLED_MESSAGES.NO_READY_RECORDS,
    );
  });

  it("shows NO_NORMALIZED_RECORDS when batch has zero normalized records", () => {
    render(
      <NormalizedRecordsPromotionPanel
        batchId="39"
        recordKind=""
        tableUnavailable={false}
        approvedInBatch={0}
        pendingInBatch={0}
        normalizedInBatch={0}
        onCompleted={vi.fn()}
        onToast={vi.fn()}
      />,
    );

    expect(screen.getByTestId("promote-disabled-reason")).toHaveTextContent(
      PROMOTE_DISABLED_MESSAGES.NO_NORMALIZED_RECORDS,
    );
  });

  it("shows dry-run summary and ALL_BLOCKED when every approved record is blocked", async () => {
    promoteNormalizedRecords.mockResolvedValue({
      dry_run: true,
      requested: 3,
      promoted: 0,
      would_promote: 0,
      skipped: 0,
      would_skip: 0,
      failed: 0,
      would_fail: 3,
      items: [],
      summary_by_blocker: { EMPLOYEE_REQUIRED: 3 },
    });

    render(
      <NormalizedRecordsPromotionPanel
        batchId="39"
        recordKind=""
        tableUnavailable={false}
        approvedInBatch={3}
        normalizedInBatch={10}
        onCompleted={vi.fn()}
        onToast={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Dry Run" }));

    await waitFor(() => {
      expect(screen.getByTestId("promotion-dry-run-summary")).toBeInTheDocument();
    });

    expect(screen.getByTestId("promotion-dry-run-summary")).toHaveTextContent("Approved");
    expect(screen.getByTestId("promotion-dry-run-summary")).toHaveTextContent("Would promote");
    expect(screen.getByTestId("promotion-dry-run-summary")).toHaveTextContent("Blocked");
    expect(screen.getByTestId("promotion-dry-run-summary")).toHaveTextContent(
      "Сотрудник не привязан (отсутствует employee_id): 3",
    );
    expect(screen.getByTestId("promote-disabled-reason")).toHaveTextContent(
      PROMOTE_DISABLED_MESSAGES.ALL_BLOCKED,
    );
    expect(screen.getByRole("button", { name: "Promote" })).toBeDisabled();
  });

  it("enables Promote after dry-run with promotable records", async () => {
    promoteNormalizedRecords.mockResolvedValue({
      dry_run: true,
      requested: 3,
      promoted: 0,
      would_promote: 2,
      skipped: 0,
      would_skip: 1,
      failed: 0,
      would_fail: 0,
      items: [],
      summary_by_blocker: {},
    });

    render(
      <NormalizedRecordsPromotionPanel
        batchId="39"
        recordKind=""
        tableUnavailable={false}
        approvedInBatch={3}
        normalizedInBatch={10}
        onCompleted={vi.fn()}
        onToast={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Dry Run" }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Promote" })).toBeEnabled();
    });
    expect(screen.queryByTestId("promote-disabled-reason")).not.toBeInTheDocument();
  });
});
