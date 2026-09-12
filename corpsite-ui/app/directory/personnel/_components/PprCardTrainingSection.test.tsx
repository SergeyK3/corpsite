import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ImportedTrainingReviewBlock } from "./PprCardTrainingSection";

const listTrainingReviewRecordsMock = vi.fn();
const patchTrainingReviewRecordMock = vi.fn();
const submitOwnTrainingReviewProposalMock = vi.fn();

vi.mock("../_lib/importApi.client", () => ({
  listTrainingReviewRecords: (...args: unknown[]) => listTrainingReviewRecordsMock(...args),
  patchTrainingReviewRecord: (...args: unknown[]) => patchTrainingReviewRecordMock(...args),
  submitOwnTrainingReviewProposal: (...args: unknown[]) => submitOwnTrainingReviewProposalMock(...args),
}));

vi.mock("@/lib/currentUser", () => ({
  useCurrentUser: () => ({ has_personnel_admin: true, employee_id: null }),
}));

const record = {
  normalized_record_id: 501,
  title: "1. Практический курс",
  provider: "Учебный центр",
  hours: 54,
  training_review: {
    version: 1,
    status: "REQUIRES_REVIEW" as const,
    dates: {
      start_date: "2024-01-01",
      end_date: "2024-01-09",
      start_date_quality: "CALCULATED" as const,
      end_date_quality: "CALCULATED" as const,
    },
    reviewer: null,
    reviewed_at: null,
    proposal: null,
    history: [],
  },
};

const summary = {
  as_of: "2026-09-12",
  timezone: "Asia/Almaty",
  confirmed_hours_last_5y: 0,
  preliminary_hours_last_5y: 54,
  required_hours: 144,
  hours_missing: 144,
  nearest_exclusion_date: null,
  hours_after_nearest_exclusion: 0,
  norm_valid_through: null,
};

describe("ImportedTrainingReviewBlock", () => {
  beforeEach(() => {
    listTrainingReviewRecordsMock.mockResolvedValue({ items: [record], total: 1, summary });
    patchTrainingReviewRecordMock.mockResolvedValue(record);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders one staging course row with review actions and without XLSX provenance", async () => {
    render(<ImportedTrainingReviewBlock employeeId="456" />);

    await screen.findByTestId("control-list-training-review-table");
    expect(screen.getByText("Название курса")).toBeInTheDocument();
    expect(screen.getByText("Качество даты")).toBeInTheDocument();
    expect(screen.getByText("Действия")).toBeInTheDocument();
    expect(screen.getByText("Практический курс")).toBeInTheDocument();
    expect(screen.getByText("Расчётная")).toBeInTheDocument();
    expect(screen.getByText("Требуется проверка")).toBeInTheDocument();
    expect(screen.queryByText("Источник")).not.toBeInTheDocument();
    expect(screen.getByText(/Подтверждено за последние 5 лет:/)).toBeInTheDocument();

    fireEvent.click(screen.getByText("Редактировать"));
    expect(screen.getByText("Сохранить изменения")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Отмена"));
    expect(patchTrainingReviewRecordMock).not.toHaveBeenCalled();

    fireEvent.click(screen.getByText("Редактировать"));
    fireEvent.click(screen.getByText("Сохранить изменения"));
    await waitFor(() => expect(patchTrainingReviewRecordMock).toHaveBeenCalledWith(501, expect.objectContaining({
      action: "edit",
      expected_version: 1,
    })));
  });

  it("shows every submitted employee-proposal difference without exposing provenance", async () => {
    listTrainingReviewRecordsMock.mockResolvedValue({
      items: [{
        ...record,
        training_review: {
          ...record.training_review,
          status: "EMPLOYEE_PROPOSED",
          proposal: {
            status: "PENDING",
            values: {
              title: "Исправленное обучение",
              provider: "Другая организация",
              start_date: "2024-02-01",
              end_date: "2024-02-05",
              hours: 40,
            },
          },
        },
      }], total: 1, summary,
    });
    render(<ImportedTrainingReviewBlock employeeId="456" />);

    await screen.findByText("Предложение сотрудника: сравните текущие и предложенные значения перед решением.");
    expect(screen.getByText("Название", { exact: true })).toBeInTheDocument();
    expect(screen.getByText(/Исправленное обучение/)).toBeInTheDocument();
    expect(screen.getByText(/Другая организация/)).toBeInTheDocument();
    expect(screen.getByText(/40/)).toBeInTheDocument();
    expect(screen.queryByText("Источник")).not.toBeInTheDocument();
  });
});
