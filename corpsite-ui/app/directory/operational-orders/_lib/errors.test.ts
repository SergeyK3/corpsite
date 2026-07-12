import { describe, expect, it } from "vitest";

import { mapOperationalOrdersApiError, isVersionConflictError } from "./errors";

describe("operational orders errors", () => {
  it("maps OO error codes", () => {
    expect(
      mapOperationalOrdersApiError({ status: 409, details: { code: "OO_WORKSPACE_FROZEN" } }, "fallback"),
    ).toBe("Рабочее пространство уже заморожено");
  });

  it("detects version conflict", () => {
    expect(isVersionConflictError({ status: 409, details: { code: "OO_DOCUMENT_VERSION_CONFLICT" } })).toBe(true);
  });
});
