import { describe, expect, it, vi } from "vitest";

import { commitMigrationRun } from "./personnelMigrationApi.client";

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
