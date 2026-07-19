import { describe, expect, it } from "vitest";

import {
  formatImportBatchDateTime,
  formatImportBatchDropdownLabel,
  formatImportBatchLabel,
  formatImportBatchNumber,
  formatImportBatchStatus,
  formatImportReportPeriod,
  isImportBatchAwaitingOperatorReview,
  isImportBatchProcessing,
  isImportBatchProcessingFailed,
  isImportBatchReviewCompleted,
  isImportBatchSuitableForInitialBaseline,
  isLegacyImportCode,
} from "./importBatchDisplay";
import {
  isSuitableInitialBaselineImport,
  selectSuitableControlListImports,
} from "./importInitialBaseline";

describe("importBatchDisplay", () => {
  it("formats import labels from business code", () => {
    const batch = { batch_id: 148, import_code: "2606-01" };
    expect(formatImportBatchLabel(batch)).toBe("Импорт 2606-01");
    expect(formatImportBatchNumber(batch)).toBe("2606-01");
  });

  it("hides legacy import codes from users", () => {
    const batch = { batch_id: 148, import_code: "legacy-148", is_legacy_import: true };
    expect(formatImportBatchLabel(batch)).toBe("Импорт 148");
    expect(formatImportBatchNumber(batch)).toBe("148");
    expect(isLegacyImportCode("legacy-148")).toBe(true);
  });

  it("formats import datetime in ru-RU locale", () => {
    expect(formatImportBatchDateTime("2026-06-16T12:00:00Z")).toMatch(/2026/);
    expect(formatImportBatchDateTime(null)).toBe("—");
  });

  it("maps internal statuses to operator-facing labels", () => {
    expect(formatImportBatchStatus("UPLOADED")).toBe("Обрабатывается");
    expect(formatImportBatchStatus("PARSED")).toBe("Обрабатывается");
    expect(formatImportBatchStatus("IN_REVIEW")).toBe("Ожидает проверки");
    expect(formatImportBatchStatus("APPLY_PENDING")).toBe("Проверка завершена");
    expect(formatImportBatchStatus("APPLIED")).toBe("Применён");
    expect(formatImportBatchStatus("PARTIALLY_APPLIED")).toBe("Частично применён");
    expect(formatImportBatchStatus("FAILED")).toBe("Ошибка обработки");
    expect(formatImportBatchStatus("CANCELLED")).toBe("Архивирован");
  });

  it("classifies lifecycle phases for workflow helpers", () => {
    expect(isImportBatchProcessing("PARSED")).toBe(true);
    expect(isImportBatchAwaitingOperatorReview("IN_REVIEW")).toBe(true);
    expect(isImportBatchReviewCompleted("APPLY_PENDING")).toBe(true);
    expect(isImportBatchProcessingFailed("FAILED")).toBe(true);
    expect(isImportBatchSuitableForInitialBaseline("APPLY_PENDING")).toBe(true);
    expect(isImportBatchSuitableForInitialBaseline("IN_REVIEW")).toBe(false);
  });

  it("formats dropdown label with file, period, upload date and status", () => {
    const label = formatImportBatchDropdownLabel({
      batch_id: 148,
      import_code: "2606-01",
      original_filename: "контрольный2606.xlsx",
      report_period: "06.2026",
      imported_at: "2026-06-16T12:00:00Z",
      status: "IN_REVIEW",
    });
    expect(label).toContain("Импорт 2606-01");
    expect(label).toContain("контрольный2606.xlsx");
    expect(label).toContain("06.2026");
    expect(label).toContain("загружен");
    expect(label).toContain("Ожидает проверки");
  });

  it("formats report period", () => {
    expect(formatImportReportPeriod("2026-06-01")).toBe("06.2026");
    expect(formatImportReportPeriod(null)).toBe("—");
  });
});

describe("importBatchDisplay + initial baseline eligibility", () => {
  type ImportBatchRowLike = {
    batch_id: number;
    import_code: string;
    file_name: string;
    imported_at: string;
    status: string;
    report_period: string;
    total_rows: number;
    valid_rows: number;
    error_rows: number;
  };

  const batch = (partial: Partial<ImportBatchRowLike>): ImportBatchRowLike => ({
    batch_id: partial.batch_id ?? 1,
    import_code: partial.import_code ?? "2606-01",
    file_name: "file.xlsx",
    imported_at: partial.imported_at ?? "2026-06-16T12:00:00Z",
    status: partial.status ?? "APPLY_PENDING",
    report_period: partial.report_period ?? "06.2026",
    total_rows: 10,
    valid_rows: 10,
    error_rows: partial.error_rows ?? 0,
  });

  it("accepts only review-completed imports without parse errors", () => {
    expect(isSuitableInitialBaselineImport(batch({ status: "APPLY_PENDING" }))).toBe(true);
    expect(isSuitableInitialBaselineImport(batch({ status: "IN_REVIEW" }))).toBe(false);
    expect(isSuitableInitialBaselineImport(batch({ status: "APPLY_PENDING", error_rows: 2 }))).toBe(false);
  });

  it("filters initial baseline imports by period and review-completed status", () => {
    const items = selectSuitableControlListImports(
      [
        batch({ batch_id: 100, status: "IN_REVIEW", imported_at: "2026-06-01T10:00:00Z" }),
        batch({ batch_id: 809, status: "APPLY_PENDING", imported_at: "2026-06-20T10:00:00Z" }),
      ],
      "2026-06-01",
    );
    expect(items.map((item) => item.batch_id)).toEqual([809]);
    expect(formatImportBatchStatus(items[0]?.status)).toBe("Проверка завершена");
  });
});
