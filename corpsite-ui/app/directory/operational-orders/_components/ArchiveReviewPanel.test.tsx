import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { listArchiveReview } from "../_lib/api";
import type { ArchiveReviewResponse, ArchiveReviewRow } from "../_lib/types";
import ArchiveReviewPanel from "./ArchiveReviewPanel";

vi.mock("../_lib/api", () => ({
  listArchiveReview: vi.fn(),
  mapOoApiError: (_error: unknown, fallback: string) => fallback,
}));

const mockedListArchiveReview = vi.mocked(listArchiveReview);

const states: ArchiveReviewRow["initial_review_state"][] = [
  "REQUISITES_PRECONFIRMED",
  "NEEDS_REQUISITES",
  "NEEDS_DOCUMENT_TYPE",
  "POSSIBLE_NON_ORDER",
];

function response(overrides: Partial<ArchiveReviewResponse> = {}): ArchiveReviewResponse {
  const items = states.map((state, index): ArchiveReviewRow => ({
    row_id: index + 1,
    excel_row: index + 45,
    archive_section: index < 2 ? "Раздел А" : "Раздел Б",
    file_name: `Приказ ${index + 1}.docx`,
    source_status: "Найден",
    initial_review_state: state,
    order_number: index === 1 ? null : index === 2 ? "298-ө" : `${index + 1}-ө`,
    order_date: index === 1 ? null : "2026-08-30",
    subject: `Предмет ${index + 1}`,
    relative_path: `Раздел\\Приказ ${index + 1}.docx`,
    duplicate_sha: index < 2,
    repeated_298: index === 2,
    official_document_id: null,
  }));
  return {
    batch: {
      batch_id: 1,
      batch_fingerprint: "c97aafa4",
      source_manifest_name: "Реестр.xlsx",
      imported_at: "2026-08-30T03:18:46Z",
      actor_user_id: 25,
    },
    stats: {
      total_records: 193,
      preconfirmed_records: 93,
      requires_processing: 100,
      archive_section_count: 26,
      state_counts: {},
      extension_counts: { ".docx": 183, ".doc": 8, ".pdf": 2 },
      duplicate_sha_excel_rows: [45, 46],
      repeated_298_excel_rows: [137, 193, 194],
    },
    sections: ["Раздел А", "Раздел Б"],
    items,
    total: 193,
    limit: 25,
    offset: 0,
    ...overrides,
  };
}

beforeEach(() => {
  mockedListArchiveReview.mockReset();
  mockedListArchiveReview.mockResolvedValue(response());
});

afterEach(() => cleanup());

describe("ArchiveReviewPanel", () => {
  it("shows loading, real-count summary, warnings and Russian review states", async () => {
    render(<ArchiveReviewPanel />);
    expect(screen.getByTestId("archive-review-loading")).toBeTruthy();

    expect(await screen.findByText(/193 записей · 93 .* · 100 требуют обработки/)).toBeTruthy();
    expect(screen.getByText("⚠ Одинаковый файл: Excel-строки 45–46")).toBeTruthy();
    expect(screen.getByText("⚠ Повтор номера 298-ө: Excel-строки 137, 193, 194")).toBeTruthy();
    expect(screen.getAllByText("Реквизиты предварительно подтверждены").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Требуется уточнить номер или дату").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Требуется проверить тип документа").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Возможно, не является приказом").length).toBeGreaterThan(0);
    expect(screen.getByTestId("archive-review-table").className).toContain("overflow-x-auto");
    expect(screen.getByRole("table", { name: "Импортированный архив производственных приказов" })).toBeTruthy();
  });

  it("sends search and all filters to the API and resets them", async () => {
    render(<ArchiveReviewPanel />);
    await screen.findByTestId("archive-review-table");

    fireEvent.change(screen.getByPlaceholderText("Имя, номер, предмет или путь"), { target: { value: "298-ө" } });
    await waitFor(() => expect(mockedListArchiveReview).toHaveBeenLastCalledWith(expect.objectContaining({ search: "298-ө" })));

    fireEvent.change(screen.getByLabelText("Состояние проверки"), { target: { value: "NEEDS_REQUISITES" } });
    await waitFor(() => expect(mockedListArchiveReview).toHaveBeenLastCalledWith(expect.objectContaining({ initial_review_state: "NEEDS_REQUISITES" })));

    fireEvent.change(screen.getByLabelText("Раздел архива"), { target: { value: "Раздел Б" } });
    fireEvent.click(screen.getByLabelText("Без номера/даты"));
    fireEvent.click(screen.getByLabelText("Duplicate SHA"));
    fireEvent.click(screen.getByLabelText("Номер 298-ө"));
    await waitFor(() => expect(mockedListArchiveReview).toHaveBeenLastCalledWith(expect.objectContaining({
      archive_section: "Раздел Б",
      only_missing_requisites: true,
      only_duplicate_sha: true,
      only_order_298: true,
    })));

    fireEvent.click(screen.getByRole("button", { name: "Сбросить фильтры" }));
    await waitFor(() => expect(mockedListArchiveReview).toHaveBeenLastCalledWith({
      search: undefined,
      initial_review_state: undefined,
      archive_section: undefined,
      only_missing_requisites: undefined,
      only_duplicate_sha: undefined,
      only_order_298: undefined,
      limit: 25,
      offset: 0,
    }));
  });

  it("loads the next page", async () => {
    render(<ArchiveReviewPanel />);
    await screen.findByText("Найдено: 193 · Страница 1 из 8");
    fireEvent.click(screen.getByRole("button", { name: "Далее" }));
    await waitFor(() => expect(mockedListArchiveReview).toHaveBeenLastCalledWith(expect.objectContaining({ offset: 25 })));
  });

  it("returns to the last valid page when the result set shrinks", async () => {
    mockedListArchiveReview
      .mockResolvedValueOnce(response())
      .mockResolvedValueOnce(response({ items: [], total: 0, offset: 25 }))
      .mockResolvedValueOnce(response({ items: [], total: 0, offset: 0 }));
    render(<ArchiveReviewPanel />);
    await screen.findByText("Найдено: 193 · Страница 1 из 8");

    fireEvent.click(screen.getByRole("button", { name: "Далее" }));
    await waitFor(() => expect(mockedListArchiveReview).toHaveBeenLastCalledWith(expect.objectContaining({ offset: 0 })));
    expect(await screen.findByText("Найдено: 0 · Страница 1 из 1")).toBeTruthy();
  });

  it("shows no-batch and empty-filter states", async () => {
    mockedListArchiveReview.mockResolvedValueOnce(response({ batch: null, stats: null, items: [], total: 0 }));
    const { unmount } = render(<ArchiveReviewPanel />);
    expect(await screen.findByTestId("archive-review-no-batch")).toBeTruthy();
    unmount();

    mockedListArchiveReview.mockResolvedValueOnce(response({ items: [], total: 0 }));
    render(<ArchiveReviewPanel />);
    expect(await screen.findByTestId("archive-review-empty-filter")).toBeTruthy();
  });

  it("shows a safe API error", async () => {
    mockedListArchiveReview.mockRejectedValueOnce(new Error("database connection secret"));
    render(<ArchiveReviewPanel />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toBe("Не удалось загрузить архив на проверке");
    expect(alert.textContent).not.toContain("database connection secret");
  });
});
