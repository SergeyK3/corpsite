// FILE: corpsite-ui/app/admin/system/_lib/adminSystemLabels.test.ts
import { describe, expect, it } from "vitest";

import { auditEventClass, metadataHasSensitiveKeys } from "./adminSystemLabels";

describe("metadataHasSensitiveKeys", () => {
  it("returns empty for safe metadata", () => {
    expect(metadataHasSensitiveKeys({ grant_id: 1, action: "test" })).toEqual([]);
  });

  it("detects password-like keys", () => {
    expect(metadataHasSensitiveKeys({ password: "x" })).toContain("password");
    expect(metadataHasSensitiveKeys({ nested: { access_token: "t" } })).toContain(
      "nested.access_token",
    );
  });
});

describe("auditEventClass", () => {
  it("highlights known security events", () => {
    expect(auditEventClass("LOGIN_FAILED")).toContain("red");
    expect(auditEventClass("UNKNOWN_EVENT")).toContain("zinc");
  });
});
