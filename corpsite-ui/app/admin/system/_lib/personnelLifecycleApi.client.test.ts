// FILE: corpsite-ui/app/admin/system/_lib/personnelLifecycleApi.client.test.ts
import { describe, expect, it, vi, beforeEach } from "vitest";

import {
  executeLifecycleRun,
  fetchEffectivePerson,
  fetchLifecycleValidation,
  fetchPersonnelEvents,
  previewLifecycleRun,
} from "./personnelLifecycleApi.client";

vi.mock("@/lib/api", () => ({
  apiFetchJson: vi.fn(),
}));

import { apiFetchJson } from "@/lib/api";

const mockedFetch = vi.mocked(apiFetchJson);

describe("personnelLifecycleApi.client", () => {
  beforeEach(() => {
    mockedFetch.mockReset();
  });

  it("previewLifecycleRun posts to run-preview", async () => {
    mockedFetch.mockResolvedValue({ run_status: "completed", duration_ms: 100 });
    await previewLifecycleRun({
      previous_snapshot_id: 1,
      snapshot_id: 2,
      refresh_cache: true,
    });
    expect(mockedFetch).toHaveBeenCalledWith("/admin/personnel/lifecycle/run-preview", {
      method: "POST",
      body: {
        previous_snapshot_id: 1,
        snapshot_id: 2,
        refresh_cache: true,
      },
    });
  });

  it("executeLifecycleRun posts to run", async () => {
    mockedFetch.mockResolvedValue({ run_status: "completed", run_id: 9 });
    await executeLifecycleRun({
      previous_snapshot_id: 1,
      snapshot_id: 2,
    });
    expect(mockedFetch).toHaveBeenCalledWith("/admin/personnel/lifecycle/run", {
      method: "POST",
      body: {
        previous_snapshot_id: 1,
        snapshot_id: 2,
      },
    });
  });

  it("fetchPersonnelEvents passes server-side filters", async () => {
    mockedFetch.mockResolvedValue({ items: [], total: 0, limit: 100, offset: 0 });
    await fetchPersonnelEvents({
      snapshot_id: 5,
      event_type: "HIRE",
      status: "detected",
      person_key: "iin:123",
      limit: 50,
      offset: 0,
    });
    expect(mockedFetch).toHaveBeenCalledWith("/admin/personnel/events", {
      query: {
        snapshot_id: 5,
        event_type: "HIRE",
        status: "detected",
        person_key: "iin:123",
        limit: 50,
        offset: 0,
      },
    });
  });

  it("fetchEffectivePerson requires person_key query", async () => {
    mockedFetch.mockResolvedValue({ person_key: "iin:123" });
    await fetchEffectivePerson({ person_key: "iin:123" });
    expect(mockedFetch).toHaveBeenCalledWith("/admin/personnel/effective-person", {
      query: { person_key: "iin:123" },
    });
  });

  it("fetchLifecycleValidation passes snapshot pair", async () => {
    mockedFetch.mockResolvedValue({ checks: [], warnings_count: 0, errors_count: 0 });
    await fetchLifecycleValidation({ previous_snapshot_id: 1, snapshot_id: 2 });
    expect(mockedFetch).toHaveBeenCalledWith("/admin/personnel/lifecycle/validation", {
      query: { previous_snapshot_id: 1, snapshot_id: 2 },
    });
  });
});
