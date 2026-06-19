import { describe, expect, it } from "vitest";

import {
  buildBlockerReasonLines,
  buildDryRunSummary,
  buildPromotionScopeLabel,
  PROMOTE_DISABLED_MESSAGES,
  resolvePromoteDisabledState,
} from "./normalizedRecordPromotionUx";
import type { PromotionDryRunResult } from "./normalizedRecordPromotionUx";
import type { PromotionResponse } from "./importApi.client";

function dryRunResult(overrides: Partial<PromotionResponse> = {}): PromotionDryRunResult {
  return {
    dry_run: true,
    requested: 3,
    promoted: 0,
    would_promote: 2,
    skipped: 0,
    would_skip: 0,
    failed: 0,
    would_fail: 1,
    items: [],
    summary_by_blocker: { EMPLOYEE_REQUIRED: 1 },
    ...overrides,
  };
}

describe("resolvePromoteDisabledState", () => {
  it("returns NO_BATCH when batch is not selected", () => {
    const state = resolvePromoteDisabledState({
      batchSelected: false,
      tableUnavailable: false,
      dryRunning: false,
      promoting: false,
      promotionResult: null,
    });
    expect(state.canPromote).toBe(false);
    expect(state.message).toBe(PROMOTE_DISABLED_MESSAGES.NO_BATCH);
    expect(state.reasonCode).toBe("NO_BATCH");
  });

  it("returns DRY_RUN_REQUIRED before dry-run", () => {
    const state = resolvePromoteDisabledState({
      batchSelected: true,
      tableUnavailable: false,
      dryRunning: false,
      promoting: false,
      promotionResult: null,
      approvedInBatch: 5,
    });
    expect(state.message).toBe(PROMOTE_DISABLED_MESSAGES.DRY_RUN_REQUIRED);
  });

  it("returns NO_READY_RECORDS when batch has zero approved before dry-run", () => {
    const state = resolvePromoteDisabledState({
      batchSelected: true,
      tableUnavailable: false,
      dryRunning: false,
      promoting: false,
      promotionResult: null,
      approvedInBatch: 0,
      normalizedInBatch: 5,
    });
    expect(state.message).toBe(PROMOTE_DISABLED_MESSAGES.NO_READY_RECORDS);
  });

  it("returns NO_NORMALIZED_RECORDS when batch has zero normalized records", () => {
    const state = resolvePromoteDisabledState({
      batchSelected: true,
      tableUnavailable: false,
      dryRunning: false,
      promoting: false,
      promotionResult: null,
      approvedInBatch: 0,
      normalizedInBatch: 0,
    });
    expect(state.message).toBe(PROMOTE_DISABLED_MESSAGES.NO_NORMALIZED_RECORDS);
    expect(state.reasonCode).toBe("NO_NORMALIZED_RECORDS");
  });

  it("returns ALL_BLOCKED when dry-run finds zero promotable approved records", () => {
    const state = resolvePromoteDisabledState({
      batchSelected: true,
      tableUnavailable: false,
      dryRunning: false,
      promoting: false,
      promotionResult: dryRunResult({ would_promote: 0, would_fail: 3, requested: 3 }),
    });
    expect(state.message).toBe(PROMOTE_DISABLED_MESSAGES.ALL_BLOCKED);
  });

  it("allows promote after successful dry-run", () => {
    const state = resolvePromoteDisabledState({
      batchSelected: true,
      tableUnavailable: false,
      dryRunning: false,
      promoting: false,
      promotionResult: dryRunResult(),
    });
    expect(state.canPromote).toBe(true);
    expect(state.message).toBeNull();
  });
});

describe("buildPromotionScopeLabel", () => {
  it("shows batch scope by default", () => {
    expect(buildPromotionScopeLabel({ batchId: 39 })).toBe("Batch #39");
  });

  it("supports future employee scope", () => {
    expect(
      buildPromotionScopeLabel({
        scope: "employee",
        employeeLabel: "Иванов И.И.",
      }),
    ).toBe("Current employee: Иванов И.И.");
  });
});

describe("buildDryRunSummary", () => {
  it("maps approved, would promote, and blocked counts", () => {
    expect(buildDryRunSummary(dryRunResult())).toEqual({
      approved: 3,
      wouldPromote: 2,
      blocked: 1,
    });
  });
});

describe("buildBlockerReasonLines", () => {
  it("groups blocker counts for display", () => {
    const lines = buildBlockerReasonLines({
      EMPLOYEE_REQUIRED: 2,
      VALIDATION_MISSING_VALID_UNTIL: 1,
      DOCUMENT_TYPE_UNRESOLVED: 1,
    });
    expect(lines).toEqual([
      {
        key: "employee",
        label: "Сотрудник не привязан (отсутствует employee_id)",
        count: 2,
      },
      {
        key: "validation",
        label: "Ошибка валидации",
        count: 1,
      },
      {
        key: "other",
        label: "Прочее",
        count: 1,
      },
    ]);
  });
});
