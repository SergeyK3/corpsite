import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import {
  TEMPLATE_TABLE_ACTIONS,
  canEditTemplate,
  isTemplateArchived,
  listStatusFilterToApi,
} from "./regularTaskTemplatePolicy";

describe("regularTaskTemplatePolicy", () => {
  it("treats inactive templates as archived", () => {
    expect(isTemplateArchived({ is_active: false })).toBe(true);
    expect(canEditTemplate({ is_active: false })).toBe(false);
    expect(canEditTemplate({ is_active: true })).toBe(true);
  });

  it("maps archived UI filter to inactive API status", () => {
    expect(listStatusFilterToApi("archived")).toBe("inactive");
    expect(listStatusFilterToApi("active")).toBe("active");
    expect(listStatusFilterToApi("all")).toBe("all");
  });

  it("does not expose delete as a primary table action", () => {
    expect(TEMPLATE_TABLE_ACTIONS).toEqual(["open", "copy", "edit", "archive"]);
    expect(TEMPLATE_TABLE_ACTIONS).not.toContain("delete");
  });
});

describe("RegularTasksAdminClient primary actions", () => {
  it("does not render Delete in the templates table actions", () => {
    const source = readFileSync(
      resolve(process.cwd(), "app/regular-tasks/_components/RegularTasksAdminClient.tsx"),
      "utf8",
    );

    expect(source).not.toMatch(/>\s*Удалить\s*</);
    expect(source).toContain("Копировать");
    expect(source).toContain("Архивировать");
    expect(source).toContain("Редактировать");
  });
});
