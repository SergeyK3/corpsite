import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("RegularTasksAdminClient copy flow", () => {
  it("opens copied template in edit mode instead of read-only view", () => {
    const source = readFileSync(
      resolve(process.cwd(), "app/regular-tasks/_components/RegularTasksAdminClient.tsx"),
      "utf8",
    );

    expect(source).toContain('setDrawerMode("edit")');
    expect(source).not.toMatch(/copy[\s\S]{0,400}setDrawerMode\("view"\)/);
  });

  it("shows form validation reason near the save action", () => {
    const source = readFileSync(
      resolve(process.cwd(), "app/regular-tasks/_components/RegularTasksAdminClient.tsx"),
      "utf8",
    );

    expect(source).toContain("{formValidationError}");
    expect(source).toContain('disabled={drawerSaving || !!formValidationError}');
  });
});
