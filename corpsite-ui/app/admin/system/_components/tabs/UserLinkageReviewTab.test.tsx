// FILE: corpsite-ui/app/admin/system/_components/tabs/UserLinkageReviewTab.test.tsx
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import UserLinkageReviewTab from "./UserLinkageReviewTab";

vi.mock("../../_lib/userLinkageReviewApi.client", () => ({
  fetchUserLinkageReviewQueue: vi.fn(),
  fetchUserLinkageReviewAudit: vi.fn(),
  approveUserLinkageReview: vi.fn(),
  rejectUserLinkageReview: vi.fn(),
  deferUserLinkageReview: vi.fn(),
  mapUserLinkageReviewApiError: (_err: unknown, fallback: string) => fallback,
}));

import {
  approveUserLinkageReview,
  deferUserLinkageReview,
  fetchUserLinkageReviewAudit,
  fetchUserLinkageReviewQueue,
  rejectUserLinkageReview,
} from "../../_lib/userLinkageReviewApi.client";

const mockedQueue = vi.mocked(fetchUserLinkageReviewQueue);
const mockedAudit = vi.mocked(fetchUserLinkageReviewAudit);
const mockedApprove = vi.mocked(approveUserLinkageReview);
const mockedReject = vi.mocked(rejectUserLinkageReview);
const mockedDefer = vi.mocked(deferUserLinkageReview);

const sampleCandidate = {
  user_id: 42,
  login: "head_100",
  user_full_name: "Sample User",
  proposed_employee_id: 100,
  employee_name: "Sample Employee",
  match_strategy: "LOGIN_SUFFIX",
  classification: "REVIEW_REQUIRED",
  confidence: "medium",
  reason_codes: ["LOGIN_SUFFIX_MATCH"],
  blockers: [],
  requires_manual_confirmation: true,
  decision_state: "PENDING",
};

describe("UserLinkageReviewTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal("prompt", vi.fn(() => "test reason"));
    mockedQueue.mockResolvedValue({
      phase: "R2",
      generated_at: "2026-06-21T00:00:00Z",
      summary: {
        review_required: 1,
        ambiguous: 0,
        approved: 0,
        rejected: 0,
        deferred: 0,
        pending: 1,
      },
      candidates: [sampleCandidate],
      total: 1,
      limit: 50,
      offset: 0,
    });
    mockedAudit.mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 });
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("renders warning banner, summary cards, table, and filters", async () => {
    render(<UserLinkageReviewTab />);

    expect(screen.getByTestId("user-linkage-review-warning")).toHaveTextContent(
      "This phase records review decisions only.",
    );

    await waitFor(() => {
      expect(screen.getByTestId("user-linkage-review-table")).toBeInTheDocument();
    });

    expect(screen.getByTestId("user-linkage-review-summary")).toBeInTheDocument();
    expect(screen.getByTestId("user-linkage-filter-classification")).toBeInTheDocument();
    expect(screen.getByTestId("user-linkage-filter-strategy")).toBeInTheDocument();
    expect(screen.getByTestId("user-linkage-filter-decision")).toBeInTheDocument();
    expect(screen.getByTestId("user-linkage-filter-search")).toBeInTheDocument();
    expect(screen.getByText("head_100")).toBeInTheDocument();
  });

  it("reloads queue when filters change", async () => {
    render(<UserLinkageReviewTab />);

    await waitFor(() => {
      expect(mockedQueue).toHaveBeenCalledTimes(1);
    });

    fireEvent.change(screen.getByTestId("user-linkage-filter-classification"), {
      target: { value: "REVIEW_REQUIRED" },
    });

    await waitFor(() => {
      expect(mockedQueue).toHaveBeenCalledWith(
        expect.objectContaining({ classification: "REVIEW_REQUIRED" }),
      );
    });
  });

  it("calls approve, reject, and defer actions", async () => {
    mockedApprove.mockResolvedValue({
      decision_id: 1,
      reviewer_user_id: 1,
      user_id: 42,
      classification: "REVIEW_REQUIRED",
      decision: "APPROVE",
    });
    mockedReject.mockResolvedValue({
      decision_id: 2,
      reviewer_user_id: 1,
      user_id: 42,
      classification: "REVIEW_REQUIRED",
      decision: "REJECT",
    });
    mockedDefer.mockResolvedValue({
      decision_id: 3,
      reviewer_user_id: 1,
      user_id: 42,
      classification: "REVIEW_REQUIRED",
      decision: "DEFER",
    });

    render(<UserLinkageReviewTab />);

    await waitFor(() => {
      expect(screen.getByTestId("user-linkage-approve-42")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("user-linkage-approve-42"));
    await waitFor(() => {
      expect(mockedApprove).toHaveBeenCalledWith(42, "test reason");
    });

    fireEvent.click(screen.getByTestId("user-linkage-reject-42"));
    await waitFor(() => {
      expect(mockedReject).toHaveBeenCalledWith(42, "test reason");
    });

    fireEvent.click(screen.getByTestId("user-linkage-defer-42"));
    await waitFor(() => {
      expect(mockedDefer).toHaveBeenCalledWith(42, "test reason");
    });
  });
});
