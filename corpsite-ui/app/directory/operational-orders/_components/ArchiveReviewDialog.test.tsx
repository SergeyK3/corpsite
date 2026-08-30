import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ComponentProps } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getArchiveReviewRow, saveArchiveReviewRow } from "../_lib/api";
import type { ArchiveReviewDetail } from "../_lib/types";
import ArchiveReviewDialogView from "./ArchiveReviewDialog";

function ArchiveReviewDialog(props: Omit<ComponentProps<typeof ArchiveReviewDialogView>, "canReview">) {
  return <ArchiveReviewDialogView canReview {...props} />;
}

vi.mock("../_lib/api", () => ({
  getArchiveReviewRow: vi.fn(),
  saveArchiveReviewRow: vi.fn(),
  mapOoApiError: (error: unknown, fallback: string) =>
    typeof error === "object" && error !== null && "status" in error && error.status === 404
      ? "Объект не найден"
      : fallback,
}));

const mockedGet = vi.mocked(getArchiveReviewRow);
const mockedSave = vi.mocked(saveArchiveReviewRow);

const terminalOutcomes: NonNullable<ArchiveReviewDetail["review_outcome"]>[] = [
  "CONFIRMED",
  "DRAFT_ORDER",
  "ORDER_ANNEX",
  "SUPPORTING_DOCUMENT",
  "DUPLICATE",
  "NOT_AN_ORDER",
];

const allOutcomes: ArchiveReviewDetail["review_outcome"][] = [
  null,
  "NEEDS_CLARIFICATION",
  ...terminalOutcomes,
];

const detail: ArchiveReviewDetail = {
  row_id: 10,
  excel_row: 45,
  archive_section: "Раздел А",
  file_name: "Приказ.docx",
  source_document_type: "Приказ",
  source_status: "Найден",
  initial_review_state: "REQUISITES_PRECONFIRMED",
  order_number: "12-ө",
  order_date: "2026-08-30",
  subject: "Исходный предмет",
  relative_path: "Раздел А\\Приказ.docx",
  duplicate_sha: true,
  repeated_298: false,
  official_document_id: null,
  confirmed_document_type: null,
  confirmed_order_number: null,
  confirmed_order_date: null,
  confirmed_subject: null,
  review_outcome: null,
  review_comment: null,
  reviewer_display_name: null,
  reviewed_at: null,
  version: 1,
};

beforeEach(() => {
  mockedGet.mockReset();
  mockedSave.mockReset();
  mockedGet.mockResolvedValue(detail);
  mockedSave.mockResolvedValue({ ...detail, review_outcome: "CONFIRMED", version: 2 });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("ArchiveReviewDialog", () => {
  it("loads detail and keeps source and official-link fields read-only", async () => {
    render(<ArchiveReviewDialog rowId={10} reviewerName="Кадровый регистратор" onClose={vi.fn()} onSaved={vi.fn()} />);
    expect(await screen.findByDisplayValue("Приказ.docx")).toHaveProperty("readOnly", true);
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Закрыть карточку" }));
    expect(screen.getByLabelText("Относительный путь")).toHaveProperty("readOnly", true);
    expect(screen.getByLabelText("Исходное состояние проверки")).toHaveValue(
      "Реквизиты предварительно подтверждены",
    );
    expect(screen.getByLabelText("Дубликат файла")).toHaveValue("Да");
    expect(screen.getByLabelText("Официальный документ")).toHaveValue("Не связан");
    expect(screen.getByText("Проверку сохранит: Кадровый регистратор")).toBeTruthy();
    expect(screen.getAllByRole("option")).toHaveLength(8);
  });

  it("ignores a stale detail response after switching to another row", async () => {
    let resolveFirst!: (value: ArchiveReviewDetail) => void;
    const first = new Promise<ArchiveReviewDetail>((resolve) => {
      resolveFirst = resolve;
    });
    mockedGet.mockReset()
      .mockReturnValueOnce(first)
      .mockResolvedValueOnce({ ...detail, row_id: 11, file_name: "Второй.docx" });

    const view = render(<ArchiveReviewDialog rowId={10} onClose={vi.fn()} onSaved={vi.fn()} />);
    view.rerender(<ArchiveReviewDialog rowId={11} onClose={vi.fn()} onSaved={vi.fn()} />);
    expect(await screen.findByDisplayValue("Второй.docx")).toBeTruthy();
    await act(async () => {
      resolveFirst({ ...detail, file_name: "Устаревший.docx" });
    });

    expect(screen.queryByDisplayValue("Устаревший.docx")).toBeNull();
    expect(screen.getByDisplayValue("Второй.docx")).toBeTruthy();
  });

  it("shows a safe not-found detail error", async () => {
    mockedGet.mockRejectedValueOnce(Object.assign(new Error("internal path"), { status: 404 }));
    render(<ArchiveReviewDialog rowId={404} onClose={vi.fn()} onSaved={vi.fn()} />);

    expect(await screen.findByText("Объект не найден")).toBeTruthy();
    expect(screen.queryByText("internal path")).toBeNull();
  });

  it("keeps confirmed fields empty for a new row and shows them only for confirmation", async () => {
    mockedGet.mockResolvedValueOnce({
      ...detail,
      source_document_type: "Приказ (предположительно)",
      subject: "Требует классификации",
    });
    render(<ArchiveReviewDialog rowId={10} onClose={vi.fn()} onSaved={vi.fn()} />);
    expect(await screen.findByDisplayValue("Приказ (предположительно)")).toHaveProperty("readOnly", true);
    expect(screen.getByDisplayValue("Требует классификации")).toHaveProperty("readOnly", true);
    expect(screen.queryByLabelText("Подтверждённый тип документа")).toBeNull();
    expect(screen.getByText("Выберите решение, чтобы заполнить необходимые поля.")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("Решение проверки"), { target: { value: "CONFIRMED" } });
    expect(screen.getByLabelText("Подтверждённый тип документа")).toHaveValue("");
    expect(screen.getByLabelText("Подтверждённый номер")).toHaveValue("");
    expect(screen.getByLabelText("Подтверждённая дата")).toHaveValue("");
    expect(screen.getByLabelText("Подтверждённое название приказа")).toHaveValue("");
    expect(screen.getByText("Введите подтверждённые тип документа, номер, дату и название приказа.")).toBeTruthy();
    expect(screen.getByLabelText("Комментарий проверяющего")).toHaveAttribute("aria-required", "false");
  });

  it.each([
    "NEEDS_CLARIFICATION",
    "DRAFT_ORDER",
    "ORDER_ANNEX",
    "SUPPORTING_DOCUMENT",
    "DUPLICATE",
    "NOT_AN_ORDER",
  ] as const)(
    "shows only the required comment for %s",
    async (outcome) => {
      render(<ArchiveReviewDialog rowId={10} onClose={vi.fn()} onSaved={vi.fn()} />);
      await screen.findByDisplayValue("Приказ.docx");
      fireEvent.change(screen.getByLabelText("Решение проверки"), { target: { value: outcome } });
      expect(screen.queryByLabelText("Подтверждённый тип документа")).toBeNull();
      expect(screen.getByLabelText("Комментарий проверяющего")).toHaveAttribute("aria-required", "true");
    },
  );

  it("clears the required-comment validation immediately after text is entered", async () => {
    render(<ArchiveReviewDialog rowId={10} onClose={vi.fn()} onSaved={vi.fn()} />);
    await screen.findByDisplayValue("Приказ.docx");
    fireEvent.change(screen.getByLabelText("Решение проверки"), { target: { value: "ORDER_ANNEX" } });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить" }));
    expect(await screen.findByText(/обязателен комментарий/i)).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Комментарий проверяющего"), { target: { value: "Приложение к строке 10" } });
    expect(screen.queryByText(/обязателен комментарий/i)).toBeNull();
  });

  it("shows the saved reviewer without exposing a technical id", async () => {
    mockedGet.mockResolvedValueOnce({
      ...detail,
      review_outcome: "DRAFT_ORDER",
      review_comment: "Предварительная версия",
      reviewer_display_name: "Кадровый регистратор",
      reviewed_at: "2026-08-30T12:00:00Z",
      version: 2,
    });
    render(<ArchiveReviewDialog rowId={10} reviewerName="Другой пользователь" onClose={vi.fn()} onSaved={vi.fn()} />);
    expect(await screen.findByText(/Проверил: Кадровый регистратор,/)).toBeTruthy();
    expect(screen.queryByText(/user.*id/i)).toBeNull();
  });

  it("validates required confirmation fields and saves with expected version", async () => {
    const onSaved = vi.fn();
    render(<ArchiveReviewDialog rowId={10} onClose={vi.fn()} onSaved={onSaved} />);
    await screen.findByDisplayValue("Приказ.docx");
    fireEvent.change(screen.getByLabelText("Решение проверки"), { target: { value: "CONFIRMED" } });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить" }));
    expect(await screen.findByText(/обязательны тип документа, номер, дата и предмет/i)).toBeTruthy();
    expect(mockedSave).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("Подтверждённый тип документа"), { target: { value: " Приказ " } });
    fireEvent.change(screen.getByLabelText("Подтверждённый номер"), { target: { value: " 12-ө " } });
    fireEvent.change(screen.getByLabelText("Подтверждённая дата"), { target: { value: "2026-08-30" } });
    fireEvent.change(screen.getByLabelText("Подтверждённое название приказа"), { target: { value: " Название " } });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить" }));
    await waitFor(() => expect(mockedSave).toHaveBeenCalledWith(10, expect.objectContaining({
      expected_version: 1,
      review_outcome: "CONFIRMED",
      confirmed_order_number: "12-ө",
    })));
    expect(onSaved).toHaveBeenCalled();
  });

  it.each([
    [403, "Недостаточно прав"],
    [409, "уже изменена"],
  ])("shows a safe %s save error", async (status, message) => {
    mockedSave.mockRejectedValueOnce(Object.assign(new Error("secret"), { status }));
    render(<ArchiveReviewDialog rowId={10} onClose={vi.fn()} onSaved={vi.fn()} />);
    await screen.findByDisplayValue("Приказ.docx");
    fireEvent.change(screen.getByLabelText("Решение проверки"), { target: { value: "DUPLICATE" } });
    fireEvent.change(screen.getByLabelText("Комментарий проверяющего"), { target: { value: "Повтор" } });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить" }));
    expect(await screen.findByText(new RegExp(message))).toBeTruthy();
    expect(screen.queryByText("secret")).toBeNull();
  });

  it("uses its own warning from the upper close button and preserves a rejected duplicate comment", async () => {
    const onClose = vi.fn();
    render(<ArchiveReviewDialog rowId={10} onClose={onClose} onSaved={vi.fn()} />);
    await enterDuplicateComment("Тестовый дубль");
    fireEvent.click(screen.getByRole("button", { name: "Закрыть карточку" }));

    expect(screen.getByRole("alertdialog", { name: "Несохранённые изменения" })).toBeTruthy();
    expect(screen.getByText(UNSAVED_WARNING)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Остаться в карточке" }));
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Комментарий проверяющего")).toHaveValue("Тестовый дубль");
  });

  it("warns from the lower cancel button for a duplicate comment", async () => {
    const onClose = vi.fn();
    render(<ArchiveReviewDialog rowId={10} onClose={onClose} onSaved={vi.fn()} />);
    await enterDuplicateComment("Дубль");
    fireEvent.click(screen.getByRole("button", { name: "Отмена" }));

    expect(screen.getByRole("alertdialog", { name: "Несохранённые изменения" })).toBeTruthy();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("closes a confirmed discard without calling PATCH", async () => {
    const onClose = vi.fn();
    render(<ArchiveReviewDialog rowId={10} onClose={onClose} onSaved={vi.fn()} />);
    await enterDuplicateComment("Дубль");
    fireEvent.click(screen.getByRole("button", { name: "Закрыть карточку" }));
    fireEvent.click(screen.getByRole("button", { name: "Закрыть без сохранения" }));

    expect(onClose).toHaveBeenCalled();
    expect(mockedSave).not.toHaveBeenCalled();
  });

  it("closes an untouched form without a warning", async () => {
    const onClose = vi.fn();
    render(<ArchiveReviewDialog rowId={10} onClose={onClose} onSaved={vi.fn()} />);
    await screen.findByDisplayValue("Приказ.docx");
    fireEvent.click(screen.getByRole("button", { name: "Закрыть карточку" }));

    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect(onClose).toHaveBeenCalled();
  });

  it.each([
    ["Подтверждённый тип документа", "Приказ"],
    ["Подтверждённый номер", "15-ө"],
    ["Подтверждённая дата", "2026-08-29"],
    ["Подтверждённое название приказа", "Название"],
  ])("treats a change in %s as dirty", async (label, value) => {
    render(<ArchiveReviewDialog rowId={10} onClose={vi.fn()} onSaved={vi.fn()} />);
    await screen.findByDisplayValue("Приказ.docx");
    fireEvent.change(screen.getByLabelText("Решение проверки"), { target: { value: "CONFIRMED" } });
    fireEvent.change(screen.getByLabelText(label), { target: { value } });
    fireEvent.change(screen.getByLabelText("Решение проверки"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Закрыть карточку" }));

    expect(screen.getByRole("alertdialog", { name: "Несохранённые изменения" })).toBeTruthy();
  });

  it("does not warn after a successful save", async () => {
    const onClose = vi.fn();
    const onSaved = vi.fn();
    mockedSave.mockResolvedValueOnce({ ...detail, review_outcome: "DUPLICATE", review_comment: "Дубль", version: 2 });
    render(<ArchiveReviewDialog rowId={10} onClose={onClose} onSaved={onSaved} />);
    await enterDuplicateComment("Дубль");
    fireEvent.click(screen.getByRole("button", { name: "Сохранить" }));
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    fireEvent.click(screen.getByRole("button", { name: "Закрыть карточку" }));

    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect(onClose).toHaveBeenCalled();
  });

  it("uses the same warning when closing by the backdrop", async () => {
    const onClose = vi.fn();
    render(<ArchiveReviewDialog rowId={10} onClose={onClose} onSaved={vi.fn()} />);
    await enterDuplicateComment("Дубль");
    fireEvent.mouseDown(screen.getByRole("presentation"));

    expect(screen.getByRole("alertdialog", { name: "Несохранённые изменения" })).toBeTruthy();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("is completely read-only without archive-review capability and never PATCHes", async () => {
    const onClose = vi.fn();
    render(
      <ArchiveReviewDialogView
        rowId={10}
        canReview={false}
        reviewerName="Руководитель отдела кадров"
        onClose={onClose}
        onSaved={vi.fn()}
      />,
    );

    expect(await screen.findByRole("dialog", { name: "Просмотр записи архива" })).toBeTruthy();
    expect(screen.getByText("Просмотр без права проверки записи.")).toBeTruthy();
    expect(screen.queryByLabelText("Решение проверки")).toBeNull();
    expect(screen.queryByLabelText("Комментарий проверяющего")).toBeNull();
    expect(screen.queryByRole("button", { name: "Сохранить" })).toBeNull();
    fireEvent.click(screen.getAllByRole("button", { name: "Закрыть" })[0]);
    expect(onClose).toHaveBeenCalled();
    expect(mockedSave).not.toHaveBeenCalled();
  });

  it.each(terminalOutcomes)("explains completed read-only state to a registrar for %s", async (reviewOutcome) => {
    mockedGet.mockResolvedValueOnce({
      ...detail,
      review_outcome: reviewOutcome,
      review_comment: reviewOutcome === "CONFIRMED" ? null : "Причина решения",
    });

    render(<ArchiveReviewDialog rowId={10} onClose={vi.fn()} onSaved={vi.fn()} />);

    expect(await screen.findByText("Проверка завершена. Запись доступна только для просмотра.")).toBeTruthy();
    expect(screen.queryByText("Просмотр без права проверки записи.")).toBeNull();
    expect(screen.queryByLabelText("Решение проверки")).toBeNull();
    expect(screen.queryByRole("button", { name: "Сохранить" })).toBeNull();
    expect(mockedSave).not.toHaveBeenCalled();
  });

  it.each(allOutcomes)("prioritizes missing capability message for outcome %s", async (reviewOutcome) => {
    mockedGet.mockResolvedValueOnce({
      ...detail,
      review_outcome: reviewOutcome,
      review_comment: reviewOutcome && reviewOutcome !== "CONFIRMED" ? "Причина решения" : null,
    });

    render(
      <ArchiveReviewDialogView
        rowId={10}
        canReview={false}
        onClose={vi.fn()}
        onSaved={vi.fn()}
      />,
    );

    expect(await screen.findByText("Просмотр без права проверки записи.")).toBeTruthy();
    expect(screen.queryByText("Проверка завершена. Запись доступна только для просмотра.")).toBeNull();
    expect(screen.queryByRole("button", { name: "Сохранить" })).toBeNull();
    expect(mockedSave).not.toHaveBeenCalled();
  });

  it.each([null, "NEEDS_CLARIFICATION"] as const)("keeps outcome %s editable for a registrar without a read-only message", async (reviewOutcome) => {
    mockedGet.mockResolvedValueOnce({
      ...detail,
      review_outcome: reviewOutcome,
      review_comment: reviewOutcome === "NEEDS_CLARIFICATION" ? "Нужно уточнение" : null,
    });

    render(<ArchiveReviewDialog rowId={10} onClose={vi.fn()} onSaved={vi.fn()} />);

    expect(await screen.findByLabelText("Решение проверки")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Сохранить" })).toBeTruthy();
    expect(screen.queryByText("Просмотр без права проверки записи.")).toBeNull();
    expect(screen.queryByText("Проверка завершена. Запись доступна только для просмотра.")).toBeNull();
  });
});

const UNSAVED_WARNING = "Есть несохранённые изменения. Закрыть карточку без сохранения?";

async function enterDuplicateComment(comment: string) {
  await screen.findByDisplayValue("Приказ.docx");
  fireEvent.change(screen.getByLabelText("Решение проверки"), { target: { value: "DUPLICATE" } });
  fireEvent.change(screen.getByLabelText("Комментарий проверяющего"), { target: { value: comment } });
}
