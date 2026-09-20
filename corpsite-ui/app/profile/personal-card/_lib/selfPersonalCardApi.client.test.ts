import { afterEach, describe, expect, it, vi } from "vitest";

import { getMyOperationalAssignment, getMyPersonalCard } from "./selfPersonalCardApi.client";

const fetchMock = vi.fn();
vi.stubGlobal("fetch", fetchMock);

vi.mock("@/lib/apiBase", () => ({ resolveApiUrl: (path: string) => `http://api.test${path}` }));
vi.mock("@/lib/api", () => ({
  buildHeaders: (headers: Record<string, string>) => headers,
  handleAuthFailureIfNeeded: () => false,
  readJsonSafe: (response: Response) => response.json(),
  toApiError: (status: number) => ({ status }),
}));

afterEach(() => fetchMock.mockReset());

describe("getMyPersonalCard", () => {
  it("uses exactly the ID-free self endpoint", async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ status: "PERSON_NOT_LINKED", card: null }), { status: 200 }));

    await expect(getMyPersonalCard()).resolves.toEqual({ status: "PERSON_NOT_LINKED", card: null });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/api/ppr/me",
      expect.objectContaining({ method: "GET" }),
    );
    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).not.toMatch(/person_id|employee_id/);
  });
});

describe("getMyOperationalAssignment", () => {
  it("uses only the ID-free self endpoint", async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ status: "READY", operational_assignment: { org_unit_name: "HR", position_name: "Specialist", operational_status: "active", employment_rate: 1, iin: "990101123456", department_group_name: null } }), { status: 200 }));

    await expect(getMyOperationalAssignment()).resolves.toMatchObject({ status: "READY" });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/api/ppr/me/operational-assignment",
      expect.objectContaining({ method: "GET" }),
    );
    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).not.toMatch(/person_id|employee_id/);
  });
});
