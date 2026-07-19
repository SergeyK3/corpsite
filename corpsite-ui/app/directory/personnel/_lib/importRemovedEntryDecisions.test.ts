import { describe, expect, it } from "vitest";

import {
  getRemovedEntryDecisionDialogBody,
  getRemovedEntryRecommendedStep,
  isRemovedEntryRoster,
  REMOVED_ENTRY_CONFIRM_REMOVAL_LABEL,
  REMOVED_ENTRY_RESTORE_LABEL,
} from "./importRemovedEntryDecisions";

describe("importRemovedEntryDecisions", () => {
  it("exposes stable action labels", () => {
    expect(REMOVED_ENTRY_RESTORE_LABEL).toBe("Восстановить запись");
    expect(REMOVED_ENTRY_CONFIRM_REMOVAL_LABEL).toBe("Подтвердить удаление");
  });

  it("detects roster removals", () => {
    expect(isRemovedEntryRoster("roster")).toBe(true);
    expect(isRemovedEntryRoster("education")).toBe(false);
  });

  it("recommends roster-specific guidance", () => {
    expect(getRemovedEntryRecommendedStep("roster")).toContain("Сотрудник");
    expect(getRemovedEntryRecommendedStep("education")).toContain("Запись");
  });

  it("describes restore vs confirm removal outcomes", () => {
    const restore = getRemovedEntryDecisionDialogBody({ record_kind: "education" }, "restore");
    const confirm = getRemovedEntryDecisionDialogBody({ record_kind: "education" }, "confirm_removal");

    expect(restore).toContain("останется в формируемом эталоне");
    expect(confirm).toContain("не должна войти в новый эталон");
  });
});
