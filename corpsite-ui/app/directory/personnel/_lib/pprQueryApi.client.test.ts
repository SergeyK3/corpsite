import { describe, expect, it, vi, afterEach } from "vitest";

import { toApiError } from "@/lib/api";
import {
  getPprByEmployeeId,
  getPprByPersonId,
  getPprSummaryByPersonId,
} from "./pprQueryApi.client";
import type { PprCompositeReadResponse } from "./pprQueryTypes";

const sampleResponse: PprCompositeReadResponse = {
  identity: {
    requested_person_id: null,
    requested_employee_id: 42,
    resolved_person_id: 100,
    merge_redirected: false,
    merge_chain: [100],
    employee_context_id: 42,
    person_status: "active",
    match_key: "iin:123",
    iin: "123456789012",
  },
  materialization: {
    materialized: true,
    lifecycle_state: "ACTIVE",
    hr_relationship_context: "EMPLOYED",
    envelope_version: 1,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-02-01T00:00:00Z",
  },
  general: {
    full_name: "Иванов Иван Иванович",
    last_name: "Иванов",
    first_name: "Иван",
    middle_name: "Иванович",
    birth_date: "1990-05-15",
    iin: "123456789012",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-02-01T00:00:00Z",
  },
  sections: {},
  events: null,
  metadata: {
    read_mode: "composite",
    source: "ppr",
    generated_at: "2024-03-01T00:00:00Z",
    warnings: [],
    transitional: false,
    merge_redirected: false,
    source_person_id: 100,
    requested_input_kind: "employee",
    requested_input_id: 42,
  },
};

describe("pprQueryApi.client", () => {
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

  it("getPprByEmployeeId calls canonical /api/ppr/employees/{id}", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockFetchResponse(sampleResponse));
    vi.stubGlobal("fetch", fetchMock);

    const result = await getPprByEmployeeId(42);

    expect(result.general.full_name).toBe("Иванов Иван Иванович");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/ppr/employees/42");
    expect(init.method).toBe("GET");
    expect(init.signal).toBeUndefined();
  });

  it("passes AbortSignal when provided", async () => {
    const controller = new AbortController();
    const fetchMock = vi.fn().mockResolvedValue(mockFetchResponse(sampleResponse));
    vi.stubGlobal("fetch", fetchMock);

    await getPprByEmployeeId("7", { signal: controller.signal });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.signal).toBe(controller.signal);
  });

  it("getPprByPersonId calls /api/ppr/persons/{id}", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockFetchResponse(sampleResponse));
    vi.stubGlobal("fetch", fetchMock);

    await getPprByPersonId(100);

    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toContain("/api/ppr/persons/100");
  });

  it("getPprSummaryByPersonId calls summary endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      mockFetchResponse({
        identity: sampleResponse.identity,
        materialization: sampleResponse.materialization,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await getPprSummaryByPersonId(100);

    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toContain("/api/ppr/persons/100/summary");
  });

  it("throws APIError on 403", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockFetchResponse({ message: "Forbidden" }, false, 403));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getPprByEmployeeId(1)).rejects.toMatchObject({ status: 403 });
  });

  it("throws APIError on 404", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockFetchResponse({ message: "Not found" }, false, 404));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getPprByEmployeeId(1)).rejects.toMatchObject({ status: 404 });
  });

  it("throws APIError on 409", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockFetchResponse({ message: "Conflict" }, false, 409));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getPprByEmployeeId(1)).rejects.toMatchObject({ status: 409 });
  });

  it("does not call legacy import-card endpoints", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockFetchResponse(sampleResponse));
    vi.stubGlobal("fetch", fetchMock);

    await getPprByEmployeeId(42);

    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).not.toContain("import-card");
    expect(url).not.toContain("/hr-import/");
  });
});

describe("mapPprCardError integration", () => {
  it("maps thrown API errors to card error kinds", async () => {
    const { mapPprCardError } = await import("./pprCardPresentation");
    expect(mapPprCardError(toApiError(403, {})).kind).toBe("access_denied");
    expect(mapPprCardError(toApiError(404, {})).kind).toBe("not_found");
    expect(mapPprCardError(toApiError(409, {})).kind).toBe("identity_conflict");
    expect(mapPprCardError(new TypeError("fetch failed")).kind).toBe("network");
  });
});
