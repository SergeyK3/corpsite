import { describe, expect, it } from "vitest";

import { workspaceStageLabel, isWorkspaceFrozen } from "./status";

describe("operational orders status", () => {
  it("maps workspace stages to Russian labels", () => {
    expect(workspaceStageLabel("SUBMITTED")).toBe("Передан");
    expect(workspaceStageLabel("DOCUMENT_PROMOTED")).toBe("Официальный проект создан");
  });

  it("detects frozen workspace", () => {
    expect(isWorkspaceFrozen("DOCUMENT_PROMOTED")).toBe(true);
    expect(isWorkspaceFrozen("EDITORIAL_PACKAGE_READY")).toBe(false);
  });
});
