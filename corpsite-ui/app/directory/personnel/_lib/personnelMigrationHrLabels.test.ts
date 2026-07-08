import { describe, expect, it } from "vitest";

import {
  migrationHrCommitError,
  migrationHrCommitUnavailableReason,
} from "./personnelMigrationHrLabels";

describe("migrationHrCommitError", () => {
  it("maps non-draft conflict to HR-friendly message", () => {
    expect(migrationHrCommitError("Run 12 is not draft (status='committed').")).toContain(
      "уже был завершён",
    );
  });

  it("maps validation errors to HR-friendly message", () => {
    expect(migrationHrCommitError("education_kind is required")).toContain(
      "не готовы к переносу",
    );
  });

  it("maps person blocker errors", () => {
    expect(migrationHrCommitError("run.person_id is required")).toContain("привязк");
  });
});

describe("migrationHrCommitUnavailableReason", () => {
  it("returns null when commit is allowed", () => {
    expect(
      migrationHrCommitUnavailableReason({
        hasItem: true,
        isDraft: true,
        hasPersonLink: true,
      }),
    ).toBeNull();
  });

  it("explains missing item", () => {
    expect(
      migrationHrCommitUnavailableReason({
        hasItem: false,
        isDraft: true,
        hasPersonLink: true,
      }),
    ).toContain("выберите запись");
  });
});
