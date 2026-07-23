import { afterEach, describe, expect, it, vi } from "vitest";

import {
  isIntakeOnBehalfDraftVersionConflict,
  saveIntakeOnBehalfDraft,
} from "./personnelApplicationsApi.client";

describe("saveIntakeOnBehalfDraft concurrency contract", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("sends expected_updated_at in PATCH body", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      text: async () =>
        JSON.stringify({
          application_id: 42,
          draft_id: 7,
          status: "editable",
          saved_at: "2026-07-23T10:00:00Z",
          draft_updated_at: "2026-07-23T10:00:01Z",
          changed_fields: ["employment_biography[0].organization"],
        }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await saveIntakeOnBehalfDraft(42, { current_step: "review" }, "2026-07-23T09:00:00.123456Z");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(String(init.body))).toEqual({
      payload: { current_step: "review" },
      expected_updated_at: "2026-07-23T09:00:00.123456Z",
    });
  });

  it("detects draft version conflict API errors", () => {
    expect(
      isIntakeOnBehalfDraftVersionConflict({
        status: 409,
        details: { detail: { code: "DRAFT_VERSION_CONFLICT", message: "conflict" } },
      }),
    ).toBe(true);
    expect(isIntakeOnBehalfDraftVersionConflict({ status: 422, details: { detail: { code: "X" } } })).toBe(
      false,
    );
  });
});
