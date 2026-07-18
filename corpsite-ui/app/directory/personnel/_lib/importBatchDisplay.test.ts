import { describe, expect, it } from "vitest";

import {
  formatImportBatchDateTime,
  formatImportBatchLabel,
  formatImportBatchNumber,
} from "./importBatchDisplay";

describe("importBatchDisplay", () => {
  it("formats import labels", () => {
    expect(formatImportBatchLabel(148)).toBe("Импорт 148");
    expect(formatImportBatchNumber(148)).toBe("148");
  });

  it("formats import datetime in ru-RU locale", () => {
    expect(formatImportBatchDateTime("2026-06-16T12:00:00Z")).toMatch(/2026/);
    expect(formatImportBatchDateTime(null)).toBe("—");
  });
});
