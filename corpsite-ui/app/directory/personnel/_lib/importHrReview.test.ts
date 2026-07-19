import { describe, expect, it } from "vitest";

import {
  buildCorrectedValueSavePayload,
  computeImportHrReviewSummary,
  filterEmployeesByStatusFilter,
  formatDifferenceProblemSummary,
  mapStatusFilterToApiParams,
} from "./importHrReview";
import type { HrReviewEmployee, HrReviewResponse } from "./mrdApi.client";

function employee(partial: Partial<HrReviewEmployee> & Pick<HrReviewEmployee, "match_key">): HrReviewEmployee {
  return {
    employee_id: null,
    full_name: partial.full_name ?? "Тест",
    position_raw: partial.position_raw ?? "Должность",
    rate: null,
    category: null,
    difference_count: partial.difference_count ?? partial.differences?.length ?? 0,
    review_status: partial.review_status ?? "PENDING",
    differences: partial.differences ?? [],
    ...partial,
  };
}

describe("importHrReview helpers", () => {
  it("maps default status filter to changed-only API params", () => {
    expect(mapStatusFilterToApiParams("needs_fix")).toEqual({ changed_only: true });
    expect(mapStatusFilterToApiParams("all")).toEqual({ changed_only: false });
  });

  it("filters employees that still need fixes", () => {
    const items = [
      employee({ match_key: "a", review_status: "PENDING" }),
      employee({ match_key: "b", review_status: "PARTIAL" }),
      employee({ match_key: "c", review_status: "REVIEWED" }),
    ];
    expect(filterEmployeesByStatusFilter(items, "needs_fix").map((item) => item.match_key)).toEqual(["a", "b"]);
  });

  it("formats real difference types for problem summaries", () => {
    expect(formatDifferenceProblemSummary({ attribute: "education_raw", field_label: "Образование" })).toBe(
      "Образование не соответствует",
    );
    expect(formatDifferenceProblemSummary({ attribute: "training_raw", field_label: "Обучение" })).toBe(
      "Тренинги не соответствуют",
    );
  });

  it("computes summary remaining separately from fixed", () => {
    const review = {
      department_summary: {
        total_employees: 2,
        without_changes: 0,
        with_changes: 2,
        awaiting_decision: 1,
        confirmed: 1,
        rejected: 0,
      },
    } as Pick<HrReviewResponse, "department_summary">;

    const employees = [
      employee({
        match_key: "a",
        differences: [
          {
            difference_id: 1,
            attribute: "education_raw",
            field_label: "Образование",
            old_value: "A",
            new_value: "B",
            detected_value: "B",
            source_label: "Импорт #1",
            lifecycle_status: "DETECTED",
            decision_status: "AWAITING",
            technical_diff_class: "CHANGED",
            record_kind: "roster",
            row_version: 1,
            actions_available: false,
          },
        ],
      }),
      employee({
        match_key: "b",
        differences: [
          {
            difference_id: 2,
            attribute: "certification_raw",
            field_label: "Медицинская категория",
            old_value: "2",
            new_value: "1",
            detected_value: "1",
            source_label: "Импорт #1",
            lifecycle_status: "CONFIRMED",
            decision_status: "CONFIRMED",
            technical_diff_class: "CHANGED",
            record_kind: "roster",
            row_version: 1,
            actions_available: false,
          },
        ],
      }),
    ];

    const summary = computeImportHrReviewSummary(review, employees);
    expect(summary.totalDiscrepancies).toBe(2);
    expect(summary.fixed).toBe(1);
    expect(summary.remaining).toBe(1);
  });

  it("defines exact save payload for corrected values", () => {
    const payload = buildCorrectedValueSavePayload({
      commandId: "hr-review-correct-test",
      correctedValue: "Вторая категория",
      difference: {
        difference_id: 77,
        attribute: "certification_raw",
        field_label: "Медицинская категория",
        old_value: "2",
        new_value: "1",
        detected_value: "1",
        source_label: "Импорт #42",
        lifecycle_status: "DETECTED",
        decision_status: "AWAITING",
        technical_diff_class: "CHANGED",
        record_kind: "roster",
        row_version: 3,
        actions_available: false,
      },
    });

    expect(payload).toEqual({
      command_id: "hr-review-correct-test",
      difference_id: 77,
      expected_row_version: 3,
      corrected_new_value: "Вторая категория",
    });
  });
});
