import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PersonnelReportsPageClient from "./PersonnelReportsPageClient";
import {
  downloadPersonnelRoster,
  getPersonnelReportOptions,
  getPersonnelRoster,
} from "../_lib/personnelReportsApi.client";

vi.mock("../_lib/personnelReportsApi.client", () => ({
  getPersonnelReportOptions: vi.fn(),
  getPersonnelRoster: vi.fn(),
  downloadPersonnelRoster: vi.fn(),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("PersonnelReportsPageClient", () => {
  it("links group and department filters and keeps report unavailable until a department is selected", async () => {
    vi.mocked(getPersonnelReportOptions).mockResolvedValue({
      groups: [
        { group_id: 1, group_name: "Клинические" },
        { group_id: 2, group_name: "Административные" },
      ],
      departments: [
        { unit_id: 10, unit_name: "Хирургия", group_id: 1 },
        { unit_id: 20, unit_name: "Кадры", group_id: 2 },
      ],
    });
    vi.mocked(getPersonnelRoster).mockResolvedValue({
      report_code: "personnel_roster",
      report_name: "Личный состав",
      generated_at: "2026-08-29T09:30:00+00:00",
      group: { id: 1, name: "Клинические" },
      department: { id: 10, name: "Хирургия" },
      items: [{ number: 1, full_name: "Абдулова А.А.", position: "Не указано", rate: "Не указано" }],
    });

    render(<PersonnelReportsPageClient />);

    const department = screen.getByRole("combobox", { name: "Отделение" });
    const download = screen.getByRole("button", { name: "Скачать Excel" });
    expect(department).toBeDisabled();
    expect(download).toBeDisabled();
    expect(screen.getByText("Выберите отделение для формирования отчёта.")).toBeInTheDocument();

    await waitFor(() => expect(screen.getByRole("option", { name: "Клинические" })).toBeInTheDocument());
    fireEvent.change(screen.getByRole("combobox", { name: "Группа отделений" }), { target: { value: "1" } });
    expect(department).not.toBeDisabled();
    expect(screen.getByRole("option", { name: "Хирургия" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Кадры" })).not.toBeInTheDocument();

    fireEvent.change(department, { target: { value: "10" } });
    expect(await screen.findByText("Абдулова А.А.")).toBeInTheDocument();
    expect(screen.getAllByText("Не указано")).toHaveLength(2);
    expect(screen.getByRole("columnheader", { name: "№" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "ФИО" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Должность" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Ставка" })).toBeInTheDocument();
    expect(download).not.toBeDisabled();
  });

  it("downloads Excel only for the selected department", async () => {
    vi.mocked(getPersonnelReportOptions).mockResolvedValue({
      groups: [{ group_id: 1, group_name: "Клинические" }],
      departments: [{ unit_id: 10, unit_name: "Хирургия", group_id: 1 }],
    });
    vi.mocked(getPersonnelRoster).mockResolvedValue({
      report_code: "personnel_roster",
      report_name: "Личный состав",
      generated_at: "2026-08-29T09:30:00+00:00",
      group: { id: 1, name: "Клинические" },
      department: { id: 10, name: "Хирургия" },
      items: [],
    });
    vi.mocked(downloadPersonnelRoster).mockResolvedValue();

    render(<PersonnelReportsPageClient />);
    await waitFor(() => expect(screen.getByRole("option", { name: "Клинические" })).toBeInTheDocument());
    fireEvent.change(screen.getByRole("combobox", { name: "Группа отделений" }), { target: { value: "1" } });
    fireEvent.change(screen.getByRole("combobox", { name: "Отделение" }), { target: { value: "10" } });
    await screen.findByText("Сотрудники не найдены.");
    fireEvent.click(screen.getByRole("button", { name: "Скачать Excel" }));
    await waitFor(() => expect(downloadPersonnelRoster).toHaveBeenCalledWith(10));
  });
});
