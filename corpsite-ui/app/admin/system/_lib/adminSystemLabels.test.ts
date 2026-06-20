// FILE: corpsite-ui/app/admin/system/_lib/adminSystemLabels.test.ts
import { describe, expect, it } from "vitest";

import {
  auditEventClass,
  formatActorLabel,
  formatAuditTargets,
  formatFieldValue,
  metadataHasSensitiveKeys,
} from "./adminSystemLabels";

describe("formatFieldValue", () => {
  it("shows NULL for empty values", () => {
    expect(formatFieldValue(null)).toBe("NULL");
    expect(formatFieldValue("x")).toBe("x");
  });
});

describe("formatActorLabel", () => {
  it("uses label when available", () => {
    expect(formatActorLabel(1, "Kim Sergey", "admin")).toBe("Kim Sergey (#1)");
  });
});

describe("formatAuditTargets", () => {
  it("formats employee target with name", () => {
    expect(
      formatAuditTargets({
        target_employee_id: 10,
        target_employee_label: "Иванов",
      }),
    ).toEqual(["Иванов (#10)"]);
  });
});

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
