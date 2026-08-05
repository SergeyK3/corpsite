import { beforeEach, describe, expect, it, vi } from "vitest";

const { apiFetchJsonMock } = vi.hoisted(() => ({ apiFetchJsonMock: vi.fn() }));

vi.mock("@/lib/api", () => ({
  apiFetchJson: apiFetchJsonMock,
}));

import {
  getIncomingDocument,
  INCOMING_INFORMATION_API_PREFIX,
  incomingInformationErrorMessage,
  incomingInformationErrorStatus,
  listIncomingDocuments,
} from "./api.client";

describe("Incoming Information browser API", () => {
  beforeEach(() => apiFetchJsonMock.mockReset());

  it("serializes the fixed page size and URL offset without changing the backend prefix", async () => {
    apiFetchJsonMock.mockResolvedValue({ items: [], total: 0, limit: 25, offset: 50 });

    await listIncomingDocuments({ limit: 25, offset: 50 });

    expect(apiFetchJsonMock).toHaveBeenCalledWith(
      "/api/incoming-information/incoming-documents",
      { query: { limit: 25, offset: 50 } },
    );
    expect(INCOMING_INFORMATION_API_PREFIX).toBe("/api/incoming-information");
  });

  it("loads detail through the factual backend route", async () => {
    apiFetchJsonMock.mockResolvedValue({ incoming_document_id: 42 });
    await getIncomingDocument(42);
    expect(apiFetchJsonMock).toHaveBeenCalledWith(
      "/api/incoming-information/incoming-documents/42",
    );
  });

  it("extracts status and safe message from API errors", () => {
    expect(incomingInformationErrorStatus({ status: 403 })).toBe(403);
    expect(incomingInformationErrorStatus(new Error("network"))).toBe(0);
    expect(incomingInformationErrorMessage({ message: "Ошибка сети" }, "fallback")).toBe("Ошибка сети");
    expect(incomingInformationErrorMessage({}, "fallback")).toBe("fallback");
  });
});
