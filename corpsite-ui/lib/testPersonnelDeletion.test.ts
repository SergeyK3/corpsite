import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({ apiFetchJson: vi.fn() }));

import { apiFetchJson } from "@/lib/api";
import {
  approveTestPersonnelDeletionRequest,
  cancelTestPersonnelDeletionRequest,
  createTestPersonnelDeletionRequest,
  executeTestPersonnelDeletionRequest,
  forgetExecutionIdempotencyKey,
  forgetIdempotencyKey,
  previewTestPersonnel,
  stableIdempotencyKey,
  stableExecutionIdempotencyKey,
  submitTestPersonnelDeletionRequest,
  testPersonnelErrorMessage,
} from "./testPersonnelDeletion";
import type { TestPersonnelExecutionSnapshot } from "./testPersonnelDeletion";

const fetchJson = vi.mocked(apiFetchJson);
const executionSnapshot: TestPersonnelExecutionSnapshot = {
  request_version: 5,
  approval_decision_id: 7,
  approval_request_version: 5,
  target_set_hash: "a".repeat(64),
  relationship_fingerprint: "b".repeat(64),
  fingerprint_version: "relationship/v2",
  relationship_policy_version: "policy/v1",
  catalog_version: "catalog/v1",
  catalog_fingerprint: "c".repeat(64),
  approval_expires_at: "2026-09-07T10:00:00Z",
  target_person_count: 1,
};

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

  it("sends only the opaque UUID and exact confirmation phrase to execution", async () => {
    await executeTestPersonnelDeletionRequest("r/1", {
      idempotencyKey: "018f4f47-6320-7a21-9f52-4a1fe0f01c5d",
      confirmationPhrase: "УДАЛИТЬ TD-0001 / 1",
      expectedSnapshot: executionSnapshot,
    });
    expect(fetchJson).toHaveBeenLastCalledWith(
      "/directory/test-personnel-deletion/requests/r%2F1/execute",
      {
        method: "POST",
        body: {
          idempotency_key: "018f4f47-6320-7a21-9f52-4a1fe0f01c5d",
          confirmation_phrase: "УДАЛИТЬ TD-0001 / 1",
          expected_snapshot: executionSnapshot,
        },
      },
    );
  });

  it("retains one canonical execution UUID for retry and rotates after completion", () => {
    const registry = new Map<string, string>();
    const first = stableExecutionIdempotencyKey(registry, "request-1:v5");
    expect(first).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i);
    expect(stableExecutionIdempotencyKey(registry, "request-1:v5")).toBe(first);
    forgetExecutionIdempotencyKey(registry, "request-1:v5");
    expect(stableExecutionIdempotencyKey(registry, "request-1:v5")).not.toBe(first);
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
