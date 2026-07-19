import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ImportHrReviewPageClient from "./ImportHrReviewPageClient";

const { getMrdHrReview, resolveImportHrReviewContext, apiAuthMe } = vi.hoisted(() => ({
  getMrdHrReview: vi.fn(),
  resolveImportHrReviewContext: vi.fn(),
  apiAuthMe: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  apiAuthMe,
}));

vi.mock("@/lib/personnelNav", () => ({
  canSeeHrProcessesNav: () => true,
}));

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams("mrd_id=101"),
}));

vi.mock("../_lib/importHrReview", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../_lib/importHrReview")>();
  return {
    ...actual,
    resolveImportHrReviewContext,
  };
});

vi.mock("../_lib/mrdApi.client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../_lib/mrdApi.client")>();
  return {
    ...actual,
    getMrdHrReview,
  };
});

const BASE_REVIEW = {
  summary: {
    mrd_id: 101,
    report_period: "2026-07-01",
    version: 1,
    status: "ACTIVE",
    row_version: 1,
    entry_count: 2,
    forked_from_reference_id: null,
    is_active_for_period: true,
  },
  org_groups: [{ value: "clinical", label: "Клинические", group_id: 2 }],
  departments: [
    { org_unit_id: 10, org_unit_name: "Терапия", org_group_id: 2 },
    { org_unit_id: 11, org_unit_name: "Хирургия", org_group_id: 2 },
  ],
  department_summary: null,
  employees: { total: 0, items: [] },
};

const DEPARTMENT_REVIEW = {
  ...BASE_REVIEW,
  department_summary: {
    total_employees: 2,
    without_changes: 0,
    with_changes: 2,
    awaiting_decision: 1,
    confirmed: 1,
    rejected: 0,
  },
  employees: {
    total: 2,
    items: [
      {
        match_key: "emp:1",
        employee_id: 1,
        full_name: "Иванова А.А.",
        position_raw: "Медсестра",
        rate: null,
        category: "2",
        difference_count: 1,
        review_status: "PENDING",
        differences: [
          {
            difference_id: 501,
            attribute: "education_raw",
            field_label: "Образование",
            old_value: "Среднее",
            new_value: "Высшее",
            detected_value: "Высшее",
            source_label: "Импорт #42",
            lifecycle_status: "DETECTED",
            decision_status: "AWAITING",
            technical_diff_class: "CHANGED",
            record_kind: "roster",
            row_version: 1,
            actions_available: false,
          },
        ],
      },
      {
        match_key: "emp:2",
        employee_id: 2,
        full_name: "Петров П.П.",
        position_raw: "Врач",
        rate: null,
        category: "1",
        difference_count: 1,
        review_status: "REVIEWED",
        differences: [
          {
            difference_id: 502,
            attribute: "certification_raw",
            field_label: "Медицинская категория",
            old_value: "Вторая категория",
            new_value: "Первая категория",
            detected_value: "Первая категория",
            source_label: "Импорт #42",
            lifecycle_status: "CONFIRMED",
            decision_status: "CONFIRMED",
            technical_diff_class: "CHANGED",
            record_kind: "roster",
            row_version: 2,
            actions_available: false,
          },
        ],
      },
    ],
  },
};

describe("ImportHrReviewPageClient", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.clearAllMocks();
    apiAuthMe.mockResolvedValue({ user_id: 1, roles: ["personnel_admin"] });
    resolveImportHrReviewContext.mockResolvedValue({ mrdId: 101, reportPeriod: "2026-07-01" });
    getMrdHrReview.mockResolvedValue(BASE_REVIEW);
  });

  it("shows top summary after department selection", async () => {
    getMrdHrReview.mockImplementation(async (_mrdId, options) => {
      if (options?.org_unit_id === 10) return DEPARTMENT_REVIEW;
      return BASE_REVIEW;
    });

    render(<ImportHrReviewPageClient />);
    await waitFor(() => {
      const select = screen.getByTestId("import-review-department") as HTMLSelectElement;
      expect(select.options.length).toBeGreaterThan(1);
    });
    fireEvent.change(screen.getByTestId("import-review-department"), { target: { value: "10" } });

    await waitFor(() => expect(screen.getByTestId("import-review-summary")).toBeInTheDocument());
    expect(screen.getByTestId("summary-total-checked")).toHaveTextContent("2");
    expect(screen.getByTestId("summary-remaining")).toHaveTextContent("1");
    expect(screen.getByTestId("summary-fixed")).toHaveTextContent("1");
  });

  it("filters departments by selected group", async () => {
    render(<ImportHrReviewPageClient />);
    await waitFor(() => expect(screen.getByTestId("import-review-org-group")).toBeInTheDocument());
    fireEvent.change(screen.getByTestId("import-review-org-group"), { target: { value: "clinical" } });
    const departmentSelect = screen.getByTestId("import-review-department") as HTMLSelectElement;
    expect(departmentSelect.options.length).toBeGreaterThan(1);
  });

  it("renders one row per employee with real discrepancy types", async () => {
    getMrdHrReview.mockResolvedValue(DEPARTMENT_REVIEW);
    render(<ImportHrReviewPageClient />);
    await waitFor(() => {
      const select = screen.getByTestId("import-review-department") as HTMLSelectElement;
      expect(select.options.length).toBeGreaterThan(1);
    });
    fireEvent.change(screen.getByTestId("import-review-department"), { target: { value: "10" } });

    await waitFor(() => expect(screen.getByTestId("import-review-employees-list")).toBeInTheDocument());
    expect(screen.getAllByTestId(/^employee-row-/)).toHaveLength(1);
    expect(screen.getByText("Образование не соответствует")).toBeInTheDocument();
    expect(screen.queryByText("Петров П.П.")).not.toBeInTheDocument();
  });

  it("opens employee fields from fix-data action and keeps filters", async () => {
    getMrdHrReview.mockResolvedValue(DEPARTMENT_REVIEW);
    render(<ImportHrReviewPageClient />);
    await waitFor(() => {
      const select = screen.getByTestId("import-review-department") as HTMLSelectElement;
      expect(select.options.length).toBeGreaterThan(1);
    });
    fireEvent.change(screen.getByTestId("import-review-department"), { target: { value: "10" } });
    await waitFor(() => expect(screen.getByText("Иванова А.А.")).toBeInTheDocument());

    fireEvent.change(screen.getByTestId("import-review-search"), { target: { value: "Иван" } });
    fireEvent.click(screen.getByTestId("fix-data-emp:1"));

    expect(screen.getByText("Эталон")).toBeInTheDocument();
    expect(screen.getByText("Контрольный список")).toBeInTheDocument();
    expect(screen.getByTestId("corrected-value-501")).toBeInTheDocument();
    expect((screen.getByTestId("import-review-search") as HTMLInputElement).value).toBe("Иван");
    expect((screen.getByTestId("import-review-status") as HTMLSelectElement).value).toBe("needs_fix");

    fireEvent.click(screen.getByTestId("fix-data-emp:1"));
    expect(screen.queryByTestId("corrected-value-501")).not.toBeInTheDocument();
    expect((screen.getByTestId("import-review-search") as HTMLInputElement).value).toBe("Иван");
  });

  it("shows resolved differences in green and excludes them from remaining count", async () => {
    getMrdHrReview.mockImplementation(async (_mrdId, options) => {
      if (options?.org_unit_id === 10) return DEPARTMENT_REVIEW;
      return BASE_REVIEW;
    });

    render(<ImportHrReviewPageClient />);
    await waitFor(() => {
      const select = screen.getByTestId("import-review-department") as HTMLSelectElement;
      expect(select.options.length).toBeGreaterThan(1);
    });
    fireEvent.change(screen.getByTestId("import-review-department"), { target: { value: "10" } });
    await waitFor(() => expect(screen.getByTestId("summary-remaining")).toHaveTextContent("1"));

    fireEvent.change(screen.getByTestId("import-review-status"), { target: { value: "fixed" } });
    await waitFor(() => expect(screen.getByText("Петров П.П.")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("fix-data-emp:2"));

    const resolvedPanel = screen.getByTestId("difference-502");
    expect(resolvedPanel).toHaveAttribute("data-decision-status", "CONFIRMED");
    expect(resolvedPanel.className).toMatch(/green/);
  });
});
