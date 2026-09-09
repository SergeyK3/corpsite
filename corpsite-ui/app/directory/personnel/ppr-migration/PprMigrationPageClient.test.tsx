import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PprMigrationPageClient from "./PprMigrationPageClient";

const apiAuthMe = vi.fn();
const apiFetchJson = vi.fn();

vi.mock("@/lib/api", () => ({
  apiAuthMe: () => apiAuthMe(),
  apiFetchJson: (...args: unknown[]) => apiFetchJson(...args),
}));

const preview = {
  source_batch_id: 3,
  source_batch_status: "APPLY_PENDING",
  preview_fingerprint: "a".repeat(64),
  counts: { ELIGIBLE: 1, BLOCKED_SOURCE_MISSING: 1 },
  eligible: [{ position: 1, employee_id: 10, person_id: 20, source_batch_id: 3, source_row_id: 31, source_row_number: 5, safe_fingerprint: "b".repeat(64), display_name: "Тестовый допущенный сотрудник" }],
  blockers: [{ employee_id: null, person_id: null, source_batch_id: 3, source_row_id: 32, source_row_number: 6, category: "BLOCKED_SOURCE_MISSING", reason_code: "STAGE0_SOURCE_EMPLOYEE_MISSING", safe_detail: "STAGE0_SOURCE_EMPLOYEE_MISSING", candidate_key: "c".repeat(64), display_name: "Тестовый сотрудник без связи" }],
};

afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe("PprMigrationPageClient", () => {
  it("uses Russian HR labels, shows correction context, and confirms freeze", async () => {
    apiAuthMe.mockResolvedValue({ user_id: 1, role_code: "HR_HEAD" });
    apiFetchJson.mockImplementation((path: string) => {
      if (path.endsWith("/source-batches")) return Promise.resolve({ items: [{ batch_id: 3, status: "APPLY_PENDING", source_row_count: 2 }] });
      if (path.endsWith("/preview")) return Promise.resolve(preview);
      if (path.endsWith("/freeze")) return Promise.resolve({ stage0_cohort_run_id: 4, replay: false, counts: preview.counts });
      if (path.includes("/runs/4")) return Promise.resolve({ run: { stage0_cohort_run_id: 4, run_kind: "BASE", source_batch_id: 3, source_batch_status: "APPLY_PENDING", frozen_at: "2026-09-09T10:00:00Z", preview_fingerprint: preview.preview_fingerprint }, participants: preview.eligible });
      throw new Error(`Unexpected request ${path}`);
    });

    render(<PprMigrationPageClient />);
    expect(await screen.findByRole("button", { name: "Проверить сотрудников" })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "Проверить сотрудников" }));

    expect(await screen.findByText("Тестовый сотрудник без связи")).toBeInTheDocument();
    expect(screen.getByText("№6")).toBeInTheDocument();
    expect(screen.getByText("Строка контрольного списка пока не связана с сотрудником.")).toBeInTheDocument();
    expect(screen.queryByText("Fingerprint:")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Зафиксировать список допущенных сотрудников" }));
    expect(screen.getByTestId("stage0-freeze-confirmation")).toBeInTheDocument();
    expect(screen.getByText("Будет сохранён список из 1 допущенных сотрудников. Заблокированных сотрудников: 1; они в список не войдут.")).toBeInTheDocument();
    expect(screen.getByText("Данные личных карточек, общие сведения, образование и другие разделы на этом шаге не изменяются.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Зафиксировать список" }));
    await waitFor(() => expect(screen.getByText(/Список допущенных сотрудников зафиксирован: 1; заблокировано: 1/)).toBeInTheDocument());
    expect(screen.getByText("Список допущенных сотрудников зафиксирован", { selector: "h2" })).toBeInTheDocument();
  });
});
