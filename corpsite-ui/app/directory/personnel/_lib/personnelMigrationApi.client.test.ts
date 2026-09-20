import { describe, expect, it, vi } from "vitest";

import { applyActiveEmployeePersonCard, applyPersonLink, commitMigrationRun, runActiveEmployeePersonCardPreflight } from "./personnelMigrationApi.client";

describe("commitMigrationRun", () => {
  it("is exported as a function", () => {
    expect(typeof commitMigrationRun).toBe("function");
  });

  it("calls POST /personnel-migration/runs/{run_id}/commit", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        run: { run_id: 7, run_status: "committed", items: [] },
        committed_items: [],
        event_ids: [],
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await commitMigrationRun(7);

    expect(fetchMock).toHaveBeenCalled();
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/personnel-migration/runs/7/commit");
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({ confirm: true });

    vi.unstubAllGlobals();
  });
});

describe("applyPersonLink", () => {
  it("calls the exact directory control-list repair apply URL", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ request_id: "r", employee_id: 1, person_id: 2, decision: "CREATE", employee_full_name: "A", canonical_full_name: "A", name_corrected: false }),
    });
    vi.stubGlobal("fetch", fetchMock);
    await applyPersonLink({ employee_id: 1, normalized_record_ids: [3], expected_precondition: "p", request_id: "request-1" });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/directory/personnel/lk/control-list-repair/apply");
    expect(init.method).toBe("POST");
    vi.unstubAllGlobals();
  });
});

describe("active employee person-card API", () => {
  it("uses the ID-only preflight endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ employee_id: 228, ready: true, blockers: [], iin: { present: true, last4: "0451" }, person_candidates: [], expected_precondition: "a".repeat(64) }) });
    vi.stubGlobal("fetch", fetchMock);
    await runActiveEmployeePersonCardPreflight(228);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/directory/personnel/lk/active-employee-card/preflight");
    expect(JSON.parse(String(init.body))).toEqual({ employee_id: 228 });
    vi.unstubAllGlobals();
  });

  it("sends explicit HR confirmation only to the new apply endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ request_id: "r", employee_id: 228, person_id: 3, decision: "CREATE", employee_full_name: "Employee" }) });
    vi.stubGlobal("fetch", fetchMock);
    await applyActiveEmployeePersonCard({ employee_id: 228, expected_precondition: "a".repeat(64), request_id: "active-employee-card-228" });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/directory/personnel/lk/active-employee-card/apply");
    expect(JSON.parse(String(init.body))).toEqual({ employee_id: 228, expected_precondition: "a".repeat(64), request_id: "active-employee-card-228", hr_confirmed: true });
    vi.unstubAllGlobals();
  });
});
