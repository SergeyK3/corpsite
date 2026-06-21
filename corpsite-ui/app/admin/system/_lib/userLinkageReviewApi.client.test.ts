// FILE: corpsite-ui/app/admin/system/_lib/userLinkageReviewApi.client.test.ts
import { describe, expect, it, vi, beforeEach } from "vitest";

import {
  approveUserLinkageReview,
  deferUserLinkageReview,
  fetchUserLinkageReviewAudit,
  fetchUserLinkageReviewQueue,
  rejectUserLinkageReview,
} from "./userLinkageReviewApi.client";

vi.mock("@/lib/api", () => ({
  apiFetchJson: vi.fn(),
}));

import { apiFetchJson } from "@/lib/api";

const mockedFetch = vi.mocked(apiFetchJson);

describe("userLinkageReviewApi.client", () => {
  beforeEach(() => {
    mockedFetch.mockReset();
  });

  it("fetchUserLinkageReviewQueue calls review endpoint with filters", async () => {
    mockedFetch.mockResolvedValue({
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
      candidates: [],
      total: 0,
      limit: 100,
      offset: 0,
    });

    await fetchUserLinkageReviewQueue({
      classification: "REVIEW_REQUIRED",
      strategy: "LOGIN_SUFFIX",
      decision_state: "PENDING",
      search: "head_",
      limit: 50,
      offset: 0,
    });

    expect(mockedFetch).toHaveBeenCalledWith(
      "/admin/personnel/identity/user-linkage/review?classification=REVIEW_REQUIRED&strategy=LOGIN_SUFFIX&decision_state=PENDING&search=head_&limit=50&offset=0",
    );
  });

  it("approveUserLinkageReview posts to approve endpoint", async () => {
    mockedFetch.mockResolvedValue({ decision_id: 1, decision: "APPROVE", user_id: 9 });
    await approveUserLinkageReview(9, "ok");
    expect(mockedFetch).toHaveBeenCalledWith(
      "/admin/personnel/identity/user-linkage/review/9/approve",
      { method: "POST", body: { reason: "ok" } },
    );
  });

  it("rejectUserLinkageReview posts to reject endpoint", async () => {
    mockedFetch.mockResolvedValue({ decision_id: 2, decision: "REJECT", user_id: 9 });
    await rejectUserLinkageReview(9, "no");
    expect(mockedFetch).toHaveBeenCalledWith(
      "/admin/personnel/identity/user-linkage/review/9/reject",
      { method: "POST", body: { reason: "no" } },
    );
  });

  it("deferUserLinkageReview posts to defer endpoint", async () => {
    mockedFetch.mockResolvedValue({ decision_id: 3, decision: "DEFER", user_id: 9 });
    await deferUserLinkageReview(9);
    expect(mockedFetch).toHaveBeenCalledWith(
      "/admin/personnel/identity/user-linkage/review/9/defer",
      { method: "POST", body: { reason: null } },
    );
  });

  it("fetchUserLinkageReviewAudit calls audit endpoint", async () => {
    mockedFetch.mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 });
    await fetchUserLinkageReviewAudit({ user_id: 9, limit: 20, offset: 0 });
    expect(mockedFetch).toHaveBeenCalledWith(
      "/admin/personnel/identity/user-linkage/review/audit?user_id=9&limit=20&offset=0",
    );
  });
});
