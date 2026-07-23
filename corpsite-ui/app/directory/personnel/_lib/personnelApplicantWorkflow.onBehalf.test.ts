import { describe, expect, it } from "vitest";

import { resolveIntakeOnBehalfEditAccess } from "./personnelApplicantWorkflow";

describe("resolveIntakeOnBehalfEditAccess", () => {
  it("enables edit during intake_pending when draft is editable", () => {
    const access = resolveIntakeOnBehalfEditAccess({
      status: "intake_pending",
      intake_draft_status: "editable",
    });
    expect(access.visible).toBe(true);
    expect(access.enabled).toBe(true);
    expect(access.blockedReason).toBeNull();
  });

  it("blocks edit during intake_pending without editable draft", () => {
    const access = resolveIntakeOnBehalfEditAccess({
      status: "intake_pending",
      intake_draft_status: null,
    });
    expect(access.visible).toBe(true);
    expect(access.enabled).toBe(false);
    expect(access.blockedReason).toMatch(/не создана|недоступна/i);
  });

  it("enables edit when section rework requested during under_review", () => {
    const access = resolveIntakeOnBehalfEditAccess(
      { status: "under_review", intake_draft_status: "submitted" },
      [{ status: "accepted" }, { status: "rework_requested" }],
    );
    expect(access.visible).toBe(true);
    expect(access.enabled).toBe(true);
    expect(access.blockedReason).toBeNull();
  });

  it("enables edit for revision_requested with submitted draft", () => {
    const access = resolveIntakeOnBehalfEditAccess({
      status: "revision_requested",
      intake_draft_status: "submitted",
    });
    expect(access.visible).toBe(true);
    expect(access.enabled).toBe(true);
    expect(access.blockedReason).toBeNull();
  });

  it("blocks edit on approval stage with explanation", () => {
    const access = resolveIntakeOnBehalfEditAccess({
      status: "awaiting_director_resolution",
      intake_draft_status: "submitted",
    });
    expect(access.visible).toBe(true);
    expect(access.enabled).toBe(false);
    expect(access.blockedReason).toMatch(/согласования/i);
  });

  it("hides edit for completed application", () => {
    const access = resolveIntakeOnBehalfEditAccess({
      status: "completed",
      intake_draft_status: "submitted",
      is_read_only: true,
    });
    expect(access.visible).toBe(false);
    expect(access.enabled).toBe(false);
  });
});
