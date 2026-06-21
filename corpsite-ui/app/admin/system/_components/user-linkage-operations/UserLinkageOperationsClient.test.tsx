// FILE: corpsite-ui/app/admin/system/_components/user-linkage-operations/UserLinkageOperationsClient.test.tsx
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import UserLinkageOperationsClient from "./UserLinkageOperationsClient";

vi.mock("../../_lib/userLinkageOperationsApi.client", () => ({
  fetchOperationsRuns: vi.fn(),
  fetchOperationsItems: vi.fn(),
  fetchOperationsRun: vi.fn(),
  fetchOperationsItem: vi.fn(),
  postRepairPreview: vi.fn(),
  postRerunExecute: vi.fn(),
  mapUserLinkageOperationsApiError: (_err: unknown, fallback: string) => fallback,
}));

import {
  fetchOperationsItems,
  fetchOperationsRuns,
  postRepairPreview,
} from "../../_lib/userLinkageOperationsApi.client";

const mockedRuns = vi.mocked(fetchOperationsRuns);
const mockedItems = vi.mocked(fetchOperationsItems);
const mockedRepair = vi.mocked(postRepairPreview);

const emptyRuns = { items: [], total: 0, limit: 1, offset: 0 };
const sampleItem = {
  item_id: 501,
  run_id: 42,
  run_operation: "USER_LINKAGE_EXECUTE",
  run_status: "completed",
  user_id: 10,
  login: "user_10",
  proposed_employee_id: 100,
  employee_name: "Employee 100",
  action: "LINK",
  status: "APPLIED",
  reason_codes: [],
  created_at: "2026-06-21T12:00:00Z",
  audit_summary: {
    user_employee_linked: 1,
    user_employee_unlinked: 0,
    user_employee_link_rolled_back: 0,
  },
};

describe("UserLinkageOperationsClient", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedRuns.mockResolvedValue(emptyRuns);
    mockedItems.mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 });
  });

  afterEach(() => {
    cleanup();
  });

  it("renders dashboard with summary cards and tabs", async () => {
    mockedItems.mockResolvedValueOnce({ items: [sampleItem], total: 1, limit: 20, offset: 0 });
    mockedRuns.mockResolvedValueOnce({ items: [{ run_id: 42, actor_login: "admin" } as never], total: 1, limit: 20, offset: 0 });

    render(<UserLinkageOperationsClient />);

    expect(screen.getByTestId("user-linkage-operations-client")).toBeInTheDocument();
    expect(screen.getByText("User Linkage Operations")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByTestId("operations-dashboard-summary")).toBeInTheDocument();
    });

    expect(screen.getByTestId("user-linkage-operations-tab-runs")).toBeInTheDocument();
    expect(screen.getByTestId("user-linkage-operations-tab-repair")).toBeInTheDocument();
  });

  it("shows loading state on dashboard", () => {
    mockedRuns.mockImplementation(() => new Promise(() => {}));
    render(<UserLinkageOperationsClient />);
    expect(screen.getByTestId("operations-dashboard-loading")).toBeInTheDocument();
  });

  it("shows empty latest operations state", async () => {
    render(<UserLinkageOperationsClient />);
    await waitFor(() => {
      expect(screen.getByTestId("operations-dashboard-latest-empty")).toBeInTheDocument();
    });
  });

  it("shows dashboard error state", async () => {
    mockedRuns.mockRejectedValue(new Error("network"));
    render(<UserLinkageOperationsClient />);
    await waitFor(() => {
      expect(screen.getByText("Не удалось загрузить сводку операций")).toBeInTheDocument();
    });
  });

  it("switches to runs tab and loads runs table", async () => {
    const runRow = {
      run_id: 7,
      phase: "R2",
      operation: "USER_LINKAGE_EXECUTE",
      status: "completed",
      dry_run: false,
      actor_login: "admin",
      started_at: "2026-06-21T10:00:00Z",
      summary: {},
      item_count: 3,
      audit_summary: {
        user_employee_linked: 2,
        user_employee_unlinked: 0,
        user_employee_link_rolled_back: 0,
      },
    };

    mockedRuns.mockImplementation(async (filters = {}) => {
      if (filters.limit === 50 && filters.offset === 0) {
        return { items: [runRow], total: 1, limit: 50, offset: 0 };
      }
      return emptyRuns;
    });

    render(<UserLinkageOperationsClient />);
    await waitFor(() => expect(mockedRuns).toHaveBeenCalled());

    fireEvent.click(screen.getByTestId("user-linkage-operations-tab-runs"));

    await waitFor(() => {
      expect(screen.getByTestId("operations-runs-grid")).toBeInTheDocument();
    });
    expect(screen.getByTestId("operations-run-row-7")).toBeInTheDocument();
  });

  it("runs repair preview and shows result", async () => {
    mockedRepair.mockResolvedValue({
      phase: "R2",
      operation: "USER_LINKAGE_REPAIR_PREVIEW",
      run_id: 1,
      item_id: 2,
      dry_run: true,
      target: {},
      current_user: {},
      current_linkage: { linked: true },
      diagnosis_code: "LINK_OK",
      recommended_action: "NO_ACTION",
      execute_ready: false,
      execute_action: "SKIP_NOT_APPROVED",
      preview: {},
      review: {},
      generated_at: "2026-06-21T12:00:00Z",
    });

    render(<UserLinkageOperationsClient />);
    await waitFor(() => expect(mockedRuns).toHaveBeenCalled());

    fireEvent.click(screen.getByTestId("user-linkage-operations-tab-repair"));
    fireEvent.click(screen.getByTestId("repair-preview-mode-user"));
    fireEvent.change(screen.getByTestId("repair-preview-target-id"), { target: { value: "10" } });
    fireEvent.change(screen.getByTestId("repair-preview-reason"), {
      target: { value: "Investigate linkage for user 10 in ops UI test" },
    });
    fireEvent.click(screen.getByTestId("repair-preview-submit"));

    await waitFor(() => {
      expect(screen.getByTestId("repair-preview-result")).toBeInTheDocument();
    });
    expect(screen.getByText("LINK_OK")).toBeInTheDocument();
  });
});
