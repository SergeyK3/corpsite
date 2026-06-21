// FILE: corpsite-ui/app/admin/system/_lib/userLinkageOperationsApi.client.test.ts
import { describe, expect, it, vi, beforeEach } from "vitest";

import {
  fetchOperationsItem,
  fetchOperationsItems,
  fetchOperationsRun,
  fetchOperationsRuns,
  postRepairPreview,
  postRerunExecute,
} from "./userLinkageOperationsApi.client";

vi.mock("@/lib/api", () => ({
  apiFetchJson: vi.fn(),
}));

import { apiFetchJson } from "@/lib/api";

const mockedFetch = vi.mocked(apiFetchJson);

describe("userLinkageOperationsApi.client", () => {
  beforeEach(() => {
    mockedFetch.mockReset();
  });

  it("fetchOperationsRuns passes filters as query", async () => {
    mockedFetch.mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 });
    await fetchOperationsRuns({
      operation: "USER_LINKAGE_EXECUTE",
      status: "completed",
      actor_user_id: 5,
      limit: 25,
      offset: 10,
    });
    expect(mockedFetch).toHaveBeenCalledWith(
      "/admin/personnel/identity/user-linkage/operations/runs",
      {
        query: {
          operation: "USER_LINKAGE_EXECUTE",
          status: "completed",
          actor_user_id: 5,
          limit: 25,
          offset: 10,
        },
      },
    );
  });

  it("fetchOperationsRun loads run detail", async () => {
    mockedFetch.mockResolvedValue({ run_id: 42 });
    await fetchOperationsRun(42);
    expect(mockedFetch).toHaveBeenCalledWith(
      "/admin/personnel/identity/user-linkage/operations/runs/42",
    );
  });

  it("fetchOperationsItems passes item filters", async () => {
    mockedFetch.mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 });
    await fetchOperationsItems({
      run_id: 7,
      action: "LINK",
      status: "APPLIED",
      user_id: 101,
      employee_id: 200,
    });
    expect(mockedFetch).toHaveBeenCalledWith(
      "/admin/personnel/identity/user-linkage/operations/items",
      {
        query: {
          run_id: 7,
          action: "LINK",
          status: "APPLIED",
          user_id: 101,
          employee_id: 200,
        },
      },
    );
  });

  it("fetchOperationsItem loads item detail", async () => {
    mockedFetch.mockResolvedValue({ item_id: 99 });
    await fetchOperationsItem(99);
    expect(mockedFetch).toHaveBeenCalledWith(
      "/admin/personnel/identity/user-linkage/operations/items/99",
    );
  });

  it("postRepairPreview posts user_id and reason", async () => {
    mockedFetch.mockResolvedValue({ diagnosis_code: "LINK_OK" });
    await postRepairPreview({
      user_id: 10,
      reason: "Investigate missing link for ticket HR-9930",
    });
    expect(mockedFetch).toHaveBeenCalledWith(
      "/admin/personnel/identity/user-linkage/operations/repair-preview",
      {
        method: "POST",
        body: {
          user_id: 10,
          reason: "Investigate missing link for ticket HR-9930",
        },
      },
    );
  });

  it("postRerunExecute posts rerun payload", async () => {
    mockedFetch.mockResolvedValue({ rerun_run_id: 1 });
    await postRerunExecute({
      source_preview_run_id: 884,
      confirm_token: "sha256:abc12345",
      reason: "Re-apply after fresh APPROVE following drift fix",
    });
    expect(mockedFetch).toHaveBeenCalledWith(
      "/admin/personnel/identity/user-linkage/operations/rerun-execute",
      {
        method: "POST",
        body: {
          source_preview_run_id: 884,
          confirm_token: "sha256:abc12345",
          reason: "Re-apply after fresh APPROVE following drift fix",
        },
      },
    );
  });
});
