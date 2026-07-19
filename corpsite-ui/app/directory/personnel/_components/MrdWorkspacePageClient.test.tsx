import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import MrdWorkspacePageClient from "./MrdWorkspacePageClient";

const { getMrdHrReview, apiAuthMe } = vi.hoisted(() => ({
  getMrdHrReview: vi.fn(),
  apiAuthMe: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  apiAuthMe,
}));

vi.mock("@/lib/personnelNav", () => ({
  canSeeHrProcessesNav: () => true,
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ mrdId: "101" }),
}));

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
    without_changes: 1,
    with_changes: 1,
    awaiting_decision: 1,
    confirmed: 0,
    rejected: 0,
  },
  employees: {
    total: 1,
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
            attribute: "position_raw",
            field_label: "Должность",
            old_value: "Медсестра",
            new_value: "Старшая медсестра",
            detected_value: "Старшая медсестра",
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
    ],
  },
};

describe("MrdWorkspacePageClient", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.clearAllMocks();
    apiAuthMe.mockResolvedValue({ user_id: 1, roles: ["personnel_admin"] });
    getMrdHrReview.mockResolvedValue(BASE_REVIEW);
  });

  it("loads etalon page with human title", async () => {
    render(<MrdWorkspacePageClient />);
    await waitFor(() => {
      expect(screen.getByTestId("mrd-etalon-page")).toBeInTheDocument();
    });
    expect(screen.getByRole("heading", { name: /Эталон кадровых данных за июль 2026/i })).toBeInTheDocument();
    expect(screen.queryByText(/MRD/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/workspace/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/fork/i)).not.toBeInTheDocument();
  });

  it("defaults to changed-only mode", async () => {
    render(<MrdWorkspacePageClient />);
    await waitFor(() => expect(getMrdHrReview).toHaveBeenCalled());
    expect(screen.getByTestId("etalon-changed-only")).toBeChecked();
    expect(getMrdHrReview).toHaveBeenCalledWith(
      101,
      expect.objectContaining({ changed_only: true }),
    );
  });

  it("filters departments by selected group", async () => {
    render(<MrdWorkspacePageClient />);
    await waitFor(() => expect(screen.getByTestId("etalon-org-group")).toBeInTheDocument());
    fireEvent.change(screen.getByTestId("etalon-org-group"), { target: { value: "clinical" } });
    const departmentSelect = screen.getByTestId("etalon-department") as HTMLSelectElement;
    expect(departmentSelect.options.length).toBeGreaterThan(1);
  });

  it("loads employees for selected department with differences only", async () => {
    getMrdHrReview.mockImplementation(async (_mrdId, options) => {
      if (options?.org_unit_id === 10) return DEPARTMENT_REVIEW;
      return BASE_REVIEW;
    });
    render(<MrdWorkspacePageClient />);
    await waitFor(() => expect(screen.getByTestId("etalon-department")).toBeInTheDocument());
    fireEvent.change(screen.getByTestId("etalon-department"), { target: { value: "10" } });
    await waitFor(() => {
      expect(screen.getByTestId("etalon-employees-list")).toBeInTheDocument();
    });
    expect(screen.getByText("Иванова А.А.")).toBeInTheDocument();
    expect(screen.queryByText("Петров")).not.toBeInTheDocument();
  });

  it("expands employee card and shows was/detected values while preserving filters", async () => {
    getMrdHrReview.mockResolvedValue(DEPARTMENT_REVIEW);
    render(<MrdWorkspacePageClient />);
    await waitFor(() => expect(screen.getByTestId("etalon-department")).toBeInTheDocument());
    fireEvent.change(screen.getByTestId("etalon-department"), { target: { value: "10" } });
    await waitFor(() => expect(screen.getByText("Иванова А.А.")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Иванова А.А."));
    expect(screen.getByText("Было")).toBeInTheDocument();
    expect(screen.getByText("Обнаружено")).toBeInTheDocument();
    expect(screen.getByText("Медсестра")).toBeInTheDocument();
    expect(screen.getByText("Старшая медсестра")).toBeInTheDocument();
    expect(screen.getByTestId("etalon-changed-only")).toBeChecked();

    fireEvent.click(screen.getByText("Иванова А.А."));
    expect(screen.queryByTestId("difference-501")).not.toBeInTheDocument();
  });

  it("shows create next period action without create version label", async () => {
    render(<MrdWorkspacePageClient />);
    await waitFor(() => expect(screen.getByTestId("mrd-etalon-page")).toBeInTheDocument());
    expect(screen.queryByText("Создать версию")).not.toBeInTheDocument();
  });
});
