import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PersonnelImportTrainingPageClient from "./PersonnelImportTrainingPageClient";

vi.mock("../_lib/importApi.client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../_lib/importApi.client")>();
  return {
    ...actual,
    getDepartmentRecodingOptions: vi.fn(async () => ({
      groups: [
        {
          value: "clinical",
          label: "Клинические",
          group_id: 1,
          effective_log_group: "clinical",
          effective_log_group_name: "Клинические",
        },
      ],
      departments: [],
    })),
    listEducationProfiles: vi.fn(async () => ({
      batch_id: 39,
      total: 2,
      limit: 50,
      offset: 0,
      summary: {
        total: 2,
        with_education: 1,
        with_training: 1,
        with_certificates: 1,
        with_categories: 1,
        without_portfolio: 1,
      },
      items: [
        {
          profile_id: 2610,
          batch_id: 39,
          row_id: 2610,
          employee_id: null,
          full_name: "Ізмұрат (Нұрбапан) Мәдина Нариманқызы",
          iin: "123456789012",
          department_source: "Отделение 1",
          org_unit_id: 1,
          org_unit_name: "Терапия",
          department_group: "clinical",
          position_raw: "Медсестра",
          education_count: 1,
          training_count: 1,
          certificate_count: 1,
          category_count: 0,
          award_count: 0,
          education: {
            count: 1,
            items: [{ text: "Жетысайский высший медицинский колледж, сестринское дело, 2021" }],
            extra_count: 0,
          },
          training: {
            count: 1,
            items: [{ text: "\"Общие сестринские технологии\", , 2022г, 120 ч" }],
            extra_count: 0,
          },
          certificates: {
            count: 1,
            items: [{ text: "Сертификат г. \"Сестринское дело\", выдан 2026, до 2026-07-09" }],
            extra_count: 0,
          },
          categories: { count: 0, items: [], extra_count: 0 },
          profile_status: "active",
          review_status: "pending",
          review_status_label: "На проверке",
        },
        {
          profile_id: 2988,
          batch_id: 39,
          row_id: 2988,
          employee_id: null,
          full_name: "Абаева Гульназ Тулебаевна",
          iin: "",
          department_source: "Отделение 2",
          org_unit_id: 2,
          org_unit_name: "Приёмное",
          department_group: "clinical",
          position_raw: "Санитарка",
          education_count: 0,
          training_count: 0,
          certificate_count: 0,
          category_count: 0,
          award_count: 0,
          education: { count: 0, items: [], extra_count: 0 },
          training: { count: 0, items: [], extra_count: 0 },
          certificates: { count: 0, items: [], extra_count: 0 },
          categories: { count: 0, items: [], extra_count: 0 },
          profile_status: "active",
          review_status: "pending",
          review_status_label: "На проверке",
        },
      ],
    })),
  };
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("PersonnelImportTrainingPageClient", () => {
  it("renders summary, educational columns and real preview values", async () => {
    render(<PersonnelImportTrainingPageClient batchId={39} />);

    await waitFor(() => {
      expect(screen.getByTestId("import-training-summary")).toHaveTextContent("Всего сотрудников");
    });

    expect(screen.getByTestId("import-training-table")).toBeInTheDocument();
    expect(screen.getByText("Жетысайский высший медицинский колледж, сестринское дело, 2021")).toBeInTheDocument();
    expect(screen.getByText(/Общие сестринские технологии/)).toBeInTheDocument();
    expect(screen.getByText(/Сертификат г\. "Сестринское дело"/)).toBeInTheDocument();
    expect(screen.getAllByText("Нет сведений").length).toBeGreaterThan(0);
    expect(screen.queryByText("Медсестра")).not.toBeInTheDocument();
    expect(screen.queryByText("Санитарка")).not.toBeInTheDocument();
  });
});
