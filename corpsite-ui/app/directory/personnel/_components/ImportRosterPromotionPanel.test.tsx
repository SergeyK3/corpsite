import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ImportRosterPromotionPanel from "./ImportRosterPromotionPanel";
import type { RosterPromotionItem } from "../_lib/importApi.client";
import { REASON_TYPE_UNMATCHED_DEPARTMENT } from "../_lib/importRosterPromotionAnalysis";

const promoteImportRosterBatch = vi.fn();

vi.mock("../_lib/importApi.client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../_lib/importApi.client")>();
  return {
    ...actual,
    promoteImportRosterBatch: (...args: unknown[]) => promoteImportRosterBatch(...args),
  };
});

function makeItems(): RosterPromotionItem[] {
  return [
    {
      row_id: 1,
      outcome: "blocked",
      full_name: "Иванов Иван",
      iin: "123456789012",
      reason: "Отделение не сопоставлено: ОБЩЕБОЛЬНИЧНЫЙ ПЕРСОНАЛ",
    },
    {
      row_id: 2,
      outcome: "blocked",
      full_name: "Петров Петр",
      iin: "210987654321",
      reason: "Отделение не сопоставлено: КАБИНЕТ ТРАНСФУЗИОЛОГИИ",
    },
    {
      row_id: 3,
      outcome: "blocked",
      full_name: "Сидоров Сидор",
      iin: "111",
      reason: "ИИН отсутствует или не содержит 12 цифр",
    },
    {
      row_id: 4,
      outcome: "would_create",
      full_name: "Новиков Новик",
      iin: "999999999999",
      org_unit_name: "Терапия",
      reason: null,
    },
  ];
}

function mockPreviewResponse() {
  return {
    batch_id: 7,
    dry_run: true,
    total_rows: 4,
    summary: {
      would_create: 1,
      would_update: 0,
      already_linked: 0,
      exists: 0,
      conflict: 0,
      blocked: 3,
    },
    items: makeItems(),
  };
}

describe("ImportRosterPromotionPanel analysis UX", () => {
  afterEach(() => {
    cleanup();
    promoteImportRosterBatch.mockReset();
  });

  it("renders overview card and two-level reason summary", async () => {
    promoteImportRosterBatch.mockResolvedValue(mockPreviewResponse());

    render(<ImportRosterPromotionPanel batchId={7} />);

    const overview = await screen.findByTestId("roster-promotion-overview");
    expect(overview).toHaveTextContent("Всего сотрудников");
    expect(overview).toHaveTextContent("4");
    expect(overview).toHaveTextContent("Частая проблема");
    expect(overview).toHaveTextContent("Не сопоставлено подразделение (2)");

    expect(screen.getByTestId(`roster-reason-type-${REASON_TYPE_UNMATCHED_DEPARTMENT}`)).toHaveTextContent(
      "Не сопоставлено подразделение"
    );
    expect(
      screen.getByTestId("roster-reason-detail-Не сопоставлено подразделение: ОБЩЕБОЛЬНИЧНЫЙ ПЕРСОНАЛ")
    ).toHaveTextContent("ОБЩЕБОЛЬНИЧНЫЙ ПЕРСОНАЛ");
    expect(screen.getByTestId("roster-reason-type-invalid_iin")).toHaveTextContent("Некорректный ИИН");
    expect(
      screen.queryByTestId("roster-reason-detail-Некорректный ИИН")
    ).not.toBeInTheDocument();
  });

  it("filters table by reason type, detail, toggles selection and resets", async () => {
    promoteImportRosterBatch.mockResolvedValue(mockPreviewResponse());

    render(<ImportRosterPromotionPanel batchId={7} />);
    await screen.findByTestId("roster-reason-summary");

    fireEvent.click(screen.getByTestId(`roster-reason-type-${REASON_TYPE_UNMATCHED_DEPARTMENT}`));
    await waitFor(() => {
      expect(screen.getByTestId("roster-promotion-filter-count")).toHaveTextContent("Показано 2 из 4");
    });
    expect(screen.getByText("Иванов Иван")).toBeInTheDocument();
    expect(screen.getByText("Петров Петр")).toBeInTheDocument();
    expect(screen.queryByText("Сидоров Сидор")).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId(`roster-reason-type-${REASON_TYPE_UNMATCHED_DEPARTMENT}`));
    await waitFor(() => {
      expect(screen.getByTestId("roster-promotion-filter-count")).toHaveTextContent("Показано 4 из 4");
    });

    fireEvent.click(
      screen.getByTestId("roster-reason-detail-Не сопоставлено подразделение: КАБИНЕТ ТРАНСФУЗИОЛОГИИ")
    );
    await waitFor(() => {
      expect(screen.getByTestId("roster-promotion-filter-count")).toHaveTextContent("Показано 1 из 4");
    });
    expect(screen.getByText("Петров Петр")).toBeInTheDocument();
    expect(screen.queryByText("Иванов Иван")).not.toBeInTheDocument();

    fireEvent.click(
      screen.getByTestId("roster-reason-detail-Не сопоставлено подразделение: КАБИНЕТ ТРАНСФУЗИОЛОГИИ")
    );
    await waitFor(() => {
      expect(screen.getByTestId("roster-promotion-filter-count")).toHaveTextContent("Показано 4 из 4");
    });

    fireEvent.click(screen.getByRole("button", { name: "Сбросить" }));
    expect(screen.getByTestId("roster-promotion-filter-count")).toHaveTextContent("Показано 4 из 4");
  });

  it("filters by status, name and IIN", async () => {
    promoteImportRosterBatch.mockResolvedValue(mockPreviewResponse());

    render(<ImportRosterPromotionPanel batchId={7} />);
    const filters = await screen.findByTestId("roster-promotion-filters");

    fireEvent.change(screen.getByPlaceholderText("Поиск по ФИО", { container: filters }), {
      target: { value: "новик" },
    });
    expect(screen.getByTestId("roster-promotion-filter-count")).toHaveTextContent("Показано 1 из 4");

    fireEvent.change(screen.getByPlaceholderText("Поиск по ФИО", { container: filters }), {
      target: { value: "" },
    });
    fireEvent.change(screen.getByPlaceholderText("Поиск по ИИН", { container: filters }), {
      target: { value: "210987" },
    });
    expect(screen.getByTestId("roster-promotion-filter-count")).toHaveTextContent("Показано 1 из 4");
    expect(screen.getByText("Петров Петр")).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("Поиск по ИИН", { container: filters }), {
      target: { value: "" },
    });
    fireEvent.change(screen.getByDisplayValue("Все статусы", { container: filters }), {
      target: { value: "would_create" },
    });
    expect(screen.getByTestId("roster-promotion-filter-count")).toHaveTextContent("Показано 1 из 4");
    expect(screen.getByText("Новиков Новик")).toBeInTheDocument();
  });
});
