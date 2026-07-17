import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import OnboardingDashboardPageClient from "./OnboardingDashboardPageClient";

vi.mock("./PersonnelSubNav", () => ({
  default: () => <div data-testid="personnel-sub-nav" />,
}));

vi.mock("../_lib/employeeOnboardingApi.client", () => ({
  getOnboardingDashboard: vi.fn(async () => ({
    active_programs_count: 3,
    overdue_tasks_count: 1,
    due_soon_tasks_count: 2,
    completion_percent: 40,
    overdue_tasks: [
      {
        item_id: 1,
        onboarding_id: 10,
        title: "Ознакомление с ЛНА",
        status: "pending",
        due_date: "2026-07-01T00:00:00Z",
        priority: "normal",
        assignee_kind: "hr",
        assignee_user_id: null,
        assignee_employee_id: null,
        assignee_name: "HR User",
        employee_id: 5,
        employee_full_name: "Иванов",
        org_unit_name: "IT",
        onboarding_status: "active",
        is_overdue: true,
      },
    ],
    due_soon_tasks: [],
  })),
  mapEmployeeOnboardingApiError: (_e: unknown, fallback: string) => fallback,
}));

describe("OnboardingDashboardPageClient", () => {
  it("renders dashboard metrics", async () => {
    render(<OnboardingDashboardPageClient />);
    expect(await screen.findByTestId("onboarding-dashboard-page")).toBeInTheDocument();
    expect(await screen.findByText("3")).toBeInTheDocument();
    expect(await screen.findByText("40%")).toBeInTheDocument();
    expect(await screen.findByTestId("onboarding-dashboard-task-1")).toBeInTheDocument();
  });
});
