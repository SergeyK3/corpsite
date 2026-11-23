import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ComponentProps } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getArchiveReviewRow, listArchiveReview, saveArchiveReviewRow } from "../_lib/api";
import type { ArchiveReviewDetail, ArchiveReviewResponse, ArchiveReviewRow } from "../_lib/types";
import ArchiveReviewPanelView from "./ArchiveReviewPanel";

function ArchiveReviewPanel(props: Omit<ComponentProps<typeof ArchiveReviewPanelView>, "canReview"> = {}) {
  return <ArchiveReviewPanelView canReview {...props} />;
}

vi.mock("../_lib/api", () => ({
  listArchiveReview: vi.fn(),
  getArchiveReviewRow: vi.fn(),
  saveArchiveReviewRow: vi.fn(),
  mapOoApiError: (_error: unknown, fallback: string) => fallback,
}));

const mockedListArchiveReview = vi.mocked(listArchiveReview);
const mockedGetArchiveReviewRow = vi.mocked(getArchiveReviewRow);
const mockedSaveArchiveReviewRow = vi.mocked(saveArchiveReviewRow);

const states: ArchiveReviewRow["initial_review_state"][] = [
  "REQUISITES_PRECONFIRMED",
  "NEEDS_REQUISITES",
  "NEEDS_DOCUMENT_TYPE",
  "POSSIBLE_NON_ORDER",
];

const terminalOutcomes: Array<NonNullable<ArchiveReviewRow["review_outcome"]>> = [
  "CONFIRMED",
  "DRAFT_ORDER",
  "ORDER_ANNEX",
  "SUPPORTING_DOCUMENT",
  "DUPLICATE",
  "NOT_AN_ORDER",
];

const allOutcomes: ArchiveReviewRow["review_outcome"][] = [
  null,
  "NEEDS_CLARIFICATION",
  ...terminalOutcomes,
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
    review_outcome: null,
    reviewer_display_name: null,
    reviewed_at: null,
    version: 1,
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
      initial_quality: {
        total: 193,
        preconfirmed: 93,
        incomplete: 100,
        state_counts: {},
      },
      work_queue: {
        pending_review: 193,
        needs_clarification: 0,
        completed_review: 0,
        outcome_counts: {
          CONFIRMED: 0,
          NEEDS_CLARIFICATION: 0,
          DRAFT_ORDER: 0,
          ORDER_ANNEX: 0,
          SUPPORTING_DOCUMENT: 0,
          DUPLICATE: 0,
          NOT_AN_ORDER: 0,
        },
      },
      archive_section_count: 26,
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
  mockedGetArchiveReviewRow.mockReset();
  mockedSaveArchiveReviewRow.mockReset();
  const row = response().items[0];
  const detail: ArchiveReviewDetail = {
    ...row,
    source_document_type: "Приказ",
    confirmed_document_type: null,
    confirmed_order_number: null,
    confirmed_order_date: null,
    confirmed_subject: null,
    review_comment: null,
  };
  mockedGetArchiveReviewRow.mockResolvedValue(detail);
  mockedSaveArchiveReviewRow.mockResolvedValue({
    ...detail,
    review_outcome: "DUPLICATE",
    review_comment: "Дубль",
    reviewer_display_name: "Кадровый регистратор",
    reviewed_at: "2026-08-30T12:00:00Z",
    version: 2,
  });
});

afterEach(() => cleanup());

describe("ArchiveReviewPanel", () => {
  it("shows loading, real-count summary, warnings and Russian review states", async () => {
    render(<ArchiveReviewPanel />);
    expect(screen.getByTestId("archive-review-loading")).toBeTruthy();

    const summary = await screen.findByTestId("archive-review-summary");
    expect(summary).toHaveTextContent(/Исходное качество: 193 записей · 93 предварительно подтверждены · 100 с неполными/i);
    expect(summary).toHaveTextContent(/Рабочая очередь: 193 не проверено · 0 требуют уточнения · 0 завершено/i);
    expect(screen.getByText("⚠ Одинаковый файл: Excel-строки 45–46")).toBeTruthy();
    expect(screen.getByText("⚠ Повтор номера 298-ө: Excel-строки 137, 193, 194")).toBeTruthy();
    expect(screen.getAllByText("Реквизиты предварительно подтверждены").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Требуется уточнить номер или дату").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Требуется проверить тип документа").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Возможно, не является приказом").length).toBeGreaterThan(0);
    expect(screen.getAllByText("⚠ Дубликат файла").length).toBeGreaterThan(0);
    expect(screen.queryByText("NEEDS_REQUISITES")).toBeNull();
    expect(screen.getByTestId("archive-review-table").className).toContain("overflow-x-auto");
    expect(screen.getByRole("table", { name: "Импортированный архив производственных приказов" })).toBeTruthy();
  });

  it("sends search and all filters to the API and resets them", async () => {
    render(<ArchiveReviewPanel />);
    await screen.findByTestId("archive-review-table");

    fireEvent.change(screen.getByPlaceholderText("Имя, номер, предмет или путь"), { target: { value: "298-ө" } });
    await waitFor(() => expect(mockedListArchiveReview).toHaveBeenLastCalledWith(expect.objectContaining({ search: "298-ө" })));

    fireEvent.change(screen.getByLabelText("Исходное состояние"), { target: { value: "NEEDS_REQUISITES" } });
    await waitFor(() => expect(mockedListArchiveReview).toHaveBeenLastCalledWith(expect.objectContaining({ initial_review_state: "NEEDS_REQUISITES" })));

    fireEvent.change(screen.getByLabelText("Результат проверки"), { target: { value: "UNREVIEWED" } });
    await waitFor(() => expect(mockedListArchiveReview).toHaveBeenLastCalledWith(expect.objectContaining({ review_outcome: "UNREVIEWED" })));

    fireEvent.change(screen.getByLabelText("Раздел архива"), { target: { value: "Раздел Б" } });
    fireEvent.click(screen.getByLabelText("Без номера/даты"));
    fireEvent.click(screen.getByLabelText("Дубликат файла"));
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
      review_outcome: undefined,
      archive_section: undefined,
      only_missing_requisites: undefined,
      only_duplicate_sha: undefined,
      only_order_298: undefined,
      limit: 25,
      offset: 0,
    }));
  });

  it("shows a Russian review result and reviewer projection", async () => {
    const reviewed = {
      ...response().items[0],
      review_outcome: "SUPPORTING_DOCUMENT" as const,
      reviewer_display_name: "Кадровый регистратор",
      reviewed_at: "2026-08-30T12:00:00Z",
    };
    mockedListArchiveReview.mockResolvedValueOnce(response({ items: [reviewed], total: 1 }));
    render(<ArchiveReviewPanel />);

    expect(await screen.findByText("Документ-основание или сопроводительный документ")).toBeTruthy();
    expect(screen.getByText(/Проверил: Кадровый регистратор,/)).toBeTruthy();
    expect(screen.queryByText("SUPPORTING_DOCUMENT")).toBeNull();
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

  it("opens a row card and refreshes the row and counts after save", async () => {
    render(<ArchiveReviewPanel />);
    await screen.findByTestId("archive-review-table");
    fireEvent.click(screen.getAllByRole("button", { name: "Проверить" })[0]);
    expect(await screen.findByRole("dialog", { name: "Проверка записи архива" })).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Решение проверки"), { target: { value: "DUPLICATE" } });
    fireEvent.change(screen.getByLabelText("Комментарий проверяющего"), { target: { value: "Дубль" } });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Excel-строки 45");
    await waitFor(() => expect(mockedListArchiveReview.mock.calls.length).toBeGreaterThan(1));
  });

  it.each([
    [null, "непроверенной"],
    ["NEEDS_CLARIFICATION" as const, "требующей уточнения"],
  ])("offers review for a registrar on a %s row", async (reviewOutcome) => {
    const item = { ...response().items[0], review_outcome: reviewOutcome };
    mockedListArchiveReview.mockResolvedValueOnce(response({ items: [item], total: 1 }));

    render(<ArchiveReviewPanel />);

    expect(await screen.findByRole("button", { name: "Проверить" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Просмотреть" })).toBeNull();
  });

  it.each(terminalOutcomes)("offers viewing for a registrar on terminal outcome %s", async (reviewOutcome) => {
    const item = { ...response().items[0], review_outcome: reviewOutcome };
    mockedListArchiveReview.mockResolvedValueOnce(response({ items: [item], total: 1 }));

    render(<ArchiveReviewPanel />);

    expect(await screen.findByRole("button", { name: "Просмотреть" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Проверить" })).toBeNull();
  });

  it.each(allOutcomes)("always offers viewing without capability for outcome %s", async (reviewOutcome) => {
    const item = { ...response().items[0], review_outcome: reviewOutcome };
    mockedListArchiveReview.mockResolvedValueOnce(response({ items: [item], total: 1 }));

    render(<ArchiveReviewPanelView canReview={false} />);

    expect(await screen.findByRole("button", { name: "Просмотреть" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Проверить" })).toBeNull();
  });

  it("opens a terminal row read-only and cannot issue PATCH", async () => {
    const item = { ...response().items[0], review_outcome: "NOT_AN_ORDER" as const };
    const terminalDetail: ArchiveReviewDetail = {
      ...item,
      source_document_type: "Приказ",
      confirmed_document_type: null,
      confirmed_order_number: null,
      confirmed_order_date: null,
      confirmed_subject: null,
      review_comment: "Не относится к приказам",
    };
    mockedListArchiveReview.mockResolvedValueOnce(response({ items: [item], total: 1 }));
    mockedGetArchiveReviewRow.mockResolvedValueOnce(terminalDetail);

    render(<ArchiveReviewPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "Просмотреть" }));

    expect(await screen.findByRole("dialog", { name: "Просмотр записи архива" })).toBeTruthy();
    expect(screen.getByText("Проверка завершена. Запись доступна только для просмотра.")).toBeTruthy();
    expect(screen.queryByText("Просмотр без права проверки записи.")).toBeNull();
    expect(screen.queryByLabelText("Решение проверки")).toBeNull();
    expect(screen.getByLabelText("Комментарий проверяющего")).toHaveProperty("readOnly", true);
    expect(screen.queryByRole("button", { name: "Сохранить" })).toBeNull();
    expect(mockedSaveArchiveReviewRow).not.toHaveBeenCalled();
  });

  it("offers read-only viewing without capability and cannot issue PATCH", async () => {
    render(<ArchiveReviewPanelView canReview={false} reviewerName="Руководитель отдела кадров" />);
    await screen.findByTestId("archive-review-table");
    expect(screen.queryByRole("button", { name: "Проверить" })).toBeNull();
    fireEvent.click(screen.getAllByRole("button", { name: "Просмотреть" })[0]);
    expect(await screen.findByRole("dialog", { name: "Просмотр записи архива" })).toBeTruthy();
    expect(screen.getByText("Просмотр без права проверки записи.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Сохранить" })).toBeNull();
    expect(mockedSaveArchiveReviewRow).not.toHaveBeenCalled();
  });
});
