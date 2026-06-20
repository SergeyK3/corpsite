// FILE: corpsite-ui/app/admin/system/_lib/personnelLifecycleLabels.test.ts
import { describe, expect, it } from "vitest";

import {
  VALIDATION_CARD_CODES,
  canApproveOverride,
  canRevokeOverride,
  effectiveOverrideValue,
  findValidationCheck,
  formatDurationBetween,
  formatDurationMs,
  lifecycleStatusClass,
} from "./personnelLifecycleLabels";
import type { ValidationCheck } from "./personnelLifecycleApi.client";

describe("personnelLifecycleLabels", () => {
  it("formatDurationMs handles sub-second and minute ranges", () => {
    expect(formatDurationMs(450)).toBe("450 ms");
    expect(formatDurationMs(2500)).toBe("2.5 s");
    expect(formatDurationMs(125_000)).toBe("2m 5s");
  });

  it("formatDurationBetween computes from ISO timestamps", () => {
    expect(formatDurationBetween("2026-06-20T10:00:00.000Z", "2026-06-20T10:00:02.500Z")).toBe(
      "2.5 s",
    );
    expect(formatDurationBetween(null, "2026-06-20T10:00:02.500Z")).toBe("—");
  });

  it("lifecycleStatusClass maps known statuses", () => {
    expect(lifecycleStatusClass("completed")).toContain("emerald");
    expect(lifecycleStatusClass("failed")).toContain("red");
    expect(lifecycleStatusClass("running")).toContain("blue");
  });

  it("override action helpers respect status", () => {
    expect(canApproveOverride("pending_approval")).toBe(true);
    expect(canApproveOverride("active")).toBe(false);
    expect(canRevokeOverride("active")).toBe(true);
  });

  it("effectiveOverrideValue prefers override when active", () => {
    expect(
      effectiveOverrideValue({
        status: "active",
        canonical_value: "a",
        override_value: "b",
      }),
    ).toBe("b");
    expect(
      effectiveOverrideValue({
        status: "pending_approval",
        canonical_value: "a",
        override_value: "b",
      }),
    ).toBe("a");
  });

  it("findValidationCheck locates check by code", () => {
    const checks: ValidationCheck[] = [
      { code: "duplicate_active_overrides", severity: "ok", count: 0 },
    ];
    expect(findValidationCheck(checks, "duplicate_active_overrides")?.count).toBe(0);
    expect(findValidationCheck(checks, "missing")).toBeUndefined();
  });

  it("VALIDATION_CARD_CODES covers primary diagnostics", () => {
    expect(VALIDATION_CARD_CODES.duplicate_active_overrides.title).toBe("Duplicate overrides");
    expect(VALIDATION_CARD_CODES.outdated_effective_cache.title).toBe("Outdated cache");
  });
});
