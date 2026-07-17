import { describe, expect, it } from "vitest";

import {
  ONBOARDING_ASSIGNEE_LABELS,
  ONBOARDING_PRIORITY_LABELS,
  ONBOARDING_TASK_AUDIT_LABELS,
  onboardingAssigneeLabel,
  onboardingPriorityLabel,
  onboardingTaskAuditLabel,
  formatDueDate,
} from "./employeeOnboardingApi.client";

describe("employeeOnboardingApi labels (WP-ONBOARDING-002)", () => {
  it("maps priority labels", () => {
    expect(onboardingPriorityLabel("high")).toBe(ONBOARDING_PRIORITY_LABELS.high);
    expect(onboardingPriorityLabel("unknown")).toBe("unknown");
  });

  it("maps assignee labels", () => {
    expect(onboardingAssigneeLabel("mentor")).toBe(ONBOARDING_ASSIGNEE_LABELS.mentor);
  });

  it("maps audit action labels", () => {
    expect(onboardingTaskAuditLabel("completed")).toBe(ONBOARDING_TASK_AUDIT_LABELS.completed);
  });

  it("formats due dates", () => {
    expect(formatDueDate(null)).toBe("—");
    expect(formatDueDate("2026-07-20T12:00:00Z")).not.toBe("—");
  });
});
