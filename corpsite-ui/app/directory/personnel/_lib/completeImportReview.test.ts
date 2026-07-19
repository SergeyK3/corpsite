import { describe, expect, it } from "vitest";

import {
  buildCompleteImportReviewResolveTarget,
  formatCompleteImportReviewBlockerSummary,
  formatCompleteImportReviewBlockerTitle,
  isCompleteImportReviewDone,
} from "./completeImportReview";
import type { CompleteImportReviewBlocker } from "./importApi.client";

describe("completeImportReview helpers", () => {
  const blocker = (resolve_kind: string): CompleteImportReviewBlocker => ({
    code: "TEST",
    message: "msg",
    batch_id: 809,
    resolve_kind,
  });

  it("builds resolve targets for known blocker kinds", () => {
    expect(buildCompleteImportReviewResolveTarget(blocker("normalized_review")).href).toBe(
      "/directory/personnel/import/review?batch=809&status=pending",
    );
    expect(buildCompleteImportReviewResolveTarget(blocker("import_analytics")).href).toBe(
      "/directory/personnel/import/809",
    );
    expect(buildCompleteImportReviewResolveTarget(blocker("import_list")).href).toBe(
      "/directory/personnel/import",
    );
  });

  it("formats blocker titles", () => {
    expect(formatCompleteImportReviewBlockerTitle("ERROR_ROWS")).toBe("Ошибки парсинга Excel");
    expect(formatCompleteImportReviewBlockerTitle("PENDING_NORMALIZED")).toBe(
      "Не проверены normalized-записи",
    );
    expect(formatCompleteImportReviewBlockerTitle("PENDING_REMOVED_DECISIONS")).toBe(
      "Отсутствуют в файле без решения",
    );
  });

  it("detects completed review statuses", () => {
    expect(isCompleteImportReviewDone("APPLY_PENDING")).toBe(true);
    expect(isCompleteImportReviewDone("IN_REVIEW")).toBe(false);
  });

  it("formats inline blocker summary for disabled complete review", () => {
    expect(
      formatCompleteImportReviewBlockerSummary(
        [
          {
            code: "PENDING_NORMALIZED",
            message: "pending",
            batch_id: 809,
            resolve_kind: "normalized_review",
            count: 1975,
          },
          {
            code: "ERROR_ROWS",
            message: "errors",
            batch_id: 809,
            resolve_kind: "import_analytics",
            count: 233,
          },
        ],
        { error_rows: 233 },
      ),
    ).toBe("Импорт ожидает проверки: не проверено 1975 записей, ошибок парсинга — 233.");
  });
});
