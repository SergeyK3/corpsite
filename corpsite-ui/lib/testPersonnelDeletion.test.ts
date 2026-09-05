import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({ apiFetchJson: vi.fn() }));

import { apiFetchJson } from "@/lib/api";
import {
  approveTestPersonnelDeletionRequest,
  cancelTestPersonnelDeletionRequest,
  createTestPersonnelDeletionRequest,
  forgetIdempotencyKey,
  previewTestPersonnel,
  stableIdempotencyKey,
  submitTestPersonnelDeletionRequest,
  testPersonnelErrorMessage,
} from "./testPersonnelDeletion";

const fetchJson = vi.mocked(apiFetchJson);

beforeEach(() => fetchJson.mockReset().mockResolvedValue({}));

describe("testPersonnelDeletion API contract", () => {
  it("uses preview mask only for preview and an exact create manifest without comment", async () => {
    await previewTestPersonnel("Тест*");
    expect(fetchJson).toHaveBeenLastCalledWith("/directory/test-personnel-deletion/preview", {
      method: "POST", body: { field: "full_name", mask: "Тест*" },
    });
    await createTestPersonnelDeletionRequest({
      reason_code: "LEGACY_SYNTHETIC_TEST_DATA", original_mask: "Тест*",
      targets: [{ person_id: 1, application_id: 2 }], idempotency_key: "create-key",
    });
    const createCall = fetchJson.mock.calls.at(-1);
    expect(createCall).toEqual(["/directory/test-personnel-deletion/requests", {
      method: "POST",
      body: {
        basis: "LEGACY_MANIFEST", reason_code: "LEGACY_SYNTHETIC_TEST_DATA",
        search_field: "full_name", original_mask: "Тест*",
        targets: [{ person_id: 1, application_id: 2 }], idempotency_key: "create-key",
      },
    }]);
    expect(createCall?.[1]?.body).not.toHaveProperty("comment");
  });

  it("passes version and idempotency for submit/cancel/approve", async () => {
    await submitTestPersonnelDeletionRequest("r1", 4, "submit-key");
    expect(fetchJson).toHaveBeenLastCalledWith("/directory/test-personnel-deletion/requests/r1/submit", {
      method: "POST", body: { expected_version: 4, idempotency_key: "submit-key" },
    });
    await cancelTestPersonnelDeletionRequest("r1", 5, "cancel-key");
    expect(fetchJson).toHaveBeenLastCalledWith("/directory/test-personnel-deletion/requests/r1/cancel", {
      method: "POST", body: { expected_version: 5, idempotency_key: "cancel-key" },
    });
    await approveTestPersonnelDeletionRequest("r1", {
      version: 6, idempotencyKey: "approve-key", comment: "ok", submittedSyntheticConfirmed: true,
    });
    expect(fetchJson).toHaveBeenLastCalledWith("/directory/test-personnel-deletion/approvals/r1/approve", {
      method: "POST",
      body: {
        expected_version: 6, idempotency_key: "approve-key", comment: "ok",
        submitted_synthetic_confirmed: true,
      },
    });
  });

  it("contains no execution API", async () => {
    const deletionApi = await import("./testPersonnelDeletion");
    expect(Object.keys(deletionApi).some((name) => /execute/i.test(name))).toBe(false);
  });

  it("keeps one idempotency key for an operation retry and rotates for a new operation", () => {
    const registry = new Map<string, string>();
    const first = stableIdempotencyKey(registry, "submit", "request-1:v1");
    expect(stableIdempotencyKey(registry, "submit", "request-1:v1")).toBe(first);
    expect(stableIdempotencyKey(registry, "submit", "request-1:v2")).not.toBe(first);
    forgetIdempotencyKey(registry, "submit", "request-1:v1");
    expect(stableIdempotencyKey(registry, "submit", "request-1:v1")).not.toBe(first);
  });

  it("does not expose an unknown transport or internal error message", () => {
    expect(testPersonnelErrorMessage(new TypeError("Failed to fetch"))).toBe(
      "Не удалось связаться с сервером. Проверьте доступность сервиса и повторите попытку.",
    );
    expect(testPersonnelErrorMessage(Object.assign(new Error("secret stack detail"), { status: 500 })))
      .not.toContain("secret stack detail");
  });
});
