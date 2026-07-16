import { describe, expect, it, vi, afterEach } from "vitest";

import { toApiError } from "@/lib/api";
import {
  createExternalEmploymentByEmployee,
  createExternalEmploymentByPerson,
  supersedeExternalEmploymentByPerson,
  voidExternalEmploymentByPerson,
} from "./pprCommandApi.client";

describe("pprCommandApi.client", () => {
  function mockFetchResponse(body: unknown, ok = true, status = 200) {
    return {
      ok,
      status,
      text: async () => JSON.stringify(body),
    };
  }

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("createExternalEmploymentByPerson posts to canonical person route", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      mockFetchResponse({ status: "committed", section_record_id: 7 }, true, 201),
    );
    vi.stubGlobal("fetch", fetchMock);

    await createExternalEmploymentByPerson(501, {
      command_id: "cmd-1",
      record: {
        record_kind: "episode",
        employer_name: "Employer",
        position_title: "Role",
        started_at: "2018-01-01",
      },
    });

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/ppr/persons/501/employment-biography/records");
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toMatchObject({ command_id: "cmd-1" });
  });

  it("createExternalEmploymentByEmployee posts to employee route", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      mockFetchResponse({ status: "committed", section_record_id: 8 }, true, 201),
    );
    vi.stubGlobal("fetch", fetchMock);

    await createExternalEmploymentByEmployee(42, {
      command_id: "cmd-2",
      record: {
        record_kind: "narrative_summary",
        notes: "Summary",
      },
    });

    const [url] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/ppr/employees/42/employment-biography/records");
  });

  it("voidExternalEmploymentByPerson sends expected_updated_at", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockFetchResponse({ status: "committed" }));
    vi.stubGlobal("fetch", fetchMock);

    await voidExternalEmploymentByPerson(501, 9, {
      command_id: "cmd-void",
      reason: "duplicate",
      expected_updated_at: "2024-02-01T12:00:00Z",
    });

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/employment-biography/records/9/void");
    expect(JSON.parse(String(init.body))).toMatchObject({
      command_id: "cmd-void",
      expected_updated_at: "2024-02-01T12:00:00Z",
    });
  });

  it("supersedeExternalEmploymentByPerson posts replacement payload", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockFetchResponse({ status: "committed" }));
    vi.stubGlobal("fetch", fetchMock);

    await supersedeExternalEmploymentByPerson(501, 10, {
      command_id: "cmd-sup",
      expected_updated_at: "2024-03-01T00:00:00Z",
      replacement: {
        record_kind: "episode",
        employer_name: "New",
        position_title: "Lead",
        started_at: "2020-01-01",
      },
    });

    const [url] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/employment-biography/records/10/supersede");
  });

  it("surfaces API validation errors", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockFetchResponse({ detail: "invalid" }, false, 422));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      createExternalEmploymentByPerson(501, {
        command_id: "cmd-bad",
        record: { record_kind: "episode", employer_name: "X" },
      }),
    ).rejects.toEqual(toApiError(422, { detail: "invalid" }));
  });
});
