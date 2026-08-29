import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PersonnelReportsPageClient from "./PersonnelReportsPageClient";
import {
  downloadPersonnelRoster,
  getPersonnelReportOptions,
  getPersonnelRoster,
  type PersonnelRosterReport,
} from "../_lib/personnelReportsApi.client";

vi.mock("../_lib/personnelReportsApi.client", () => ({
  getPersonnelReportOptions: vi.fn(),
  getPersonnelRoster: vi.fn(),
  downloadPersonnelRoster: vi.fn(),
}));

const options = {
  groups: [
    { group_id: 1, group_name: "Клинические" },
    { group_id: 2, group_name: "Административные" },
  ],
  departments: [
    { unit_id: 10, unit_name: "Хирургия", group_id: 1 },
    { unit_id: 11, unit_name: "Терапия", group_id: 1 },
    { unit_id: 20, unit_name: "Кадры", group_id: 2 },
  ],
};

const report: PersonnelRosterReport = {
  report_code: "personnel_roster",
  report_name: "Личный состав",
  generated_at: "2026-08-29T09:30:00+00:00",
  filters: { group: null, department: null },
  summary: [
    {
      number: 1,
      group: { id: 1, name: "Клинические" },
      department: { id: 11, name: "Терапия" },
      employee_count: 1,
      rate_total: 1,
    },
    {
      number: 2,
      group: { id: 1, name: "Клинические" },
      department: { id: 10, name: "Хирургия" },
      employee_count: 2,
      rate_total: 0.5,
    },
  ],
  total: 3,
  total_rate: 1.5,
  missing_rate_count: 1,
  groups: [
    {
      id: 1,
      name: "Клинические",
      departments: [
        {
          id: 11,
          name: "Терапия",
          items: [
            { employee_id: 1, number: 1, full_name: "Абдулова А.А.", position: "Не указано", rate: "1", rate_value: 1 },
          ],
        },
        {
          id: 10,
          name: "Хирургия",
          items: [
            { employee_id: 2, number: 1, full_name: "Беков Б.Б.", position: "Врач", rate: "Не указано", rate_value: null },
            { employee_id: 3, number: 2, full_name: "Волкова В.В.", position: "Врач", rate: "0,5", rate_value: 0.5 },
          ],
        },
      ],
    },
  ],
  items: [
    { employee_id: 1, number: 1, full_name: "Абдулова А.А.", position: "Не указано", rate: "1", rate_value: 1 },
    { employee_id: 2, number: 1, full_name: "Беков Б.Б.", position: "Врач", rate: "Не указано", rate_value: null },
    { employee_id: 3, number: 2, full_name: "Волкова В.В.", position: "Врач", rate: "0,5", rate_value: 0.5 },
  ],
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("PersonnelReportsPageClient", () => {
  it("offers all scopes and automatically renders matching summary and grouped details", async () => {
    vi.mocked(getPersonnelReportOptions).mockResolvedValue(options);
    vi.mocked(getPersonnelRoster).mockResolvedValue(report);

    render(<PersonnelReportsPageClient />);

    expect(await screen.findByRole("option", { name: "Все группы" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Все отделения" })).toBeInTheDocument();
    await waitFor(() => expect(getPersonnelRoster).toHaveBeenCalledWith({ groupId: undefined, orgUnitId: undefined }));

    expect(await screen.findByRole("heading", { name: "Сводный состав по отделениям" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Количество человек" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Количество ставок" })).toBeInTheDocument();
    const totalRow = screen.getByText("ВСЕГО").closest("tr");
    expect(totalRow).not.toBeNull();
    expect(within(totalRow!).getByText("3")).toBeInTheDocument();
    expect(within(totalRow!).getByText("1,5")).toBeInTheDocument();
    expect(screen.getByText("Ставка не указана у 1 сотрудников")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Клинические" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Терапия" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Хирургия" })).toBeInTheDocument();
    expect(screen.getAllByText("Не указано")).toHaveLength(2);
    expect(screen.getAllByRole("columnheader", { name: "№" })).toHaveLength(3);
    expect(screen.getByRole("button", { name: "Скачать Excel" })).not.toBeDisabled();
  });

  it("filters departments by group and resets an incompatible department", async () => {
    vi.mocked(getPersonnelReportOptions).mockResolvedValue(options);
    vi.mocked(getPersonnelRoster).mockResolvedValue(report);

    render(<PersonnelReportsPageClient />);
    const group = await screen.findByRole("combobox", { name: "Группа отделений" });
    const department = screen.getByRole("combobox", { name: "Отделение" });

    fireEvent.change(department, { target: { value: "20" } });
    await waitFor(() => expect(getPersonnelRoster).toHaveBeenLastCalledWith({ groupId: undefined, orgUnitId: 20 }));
    fireEvent.change(group, { target: { value: "1" } });

    expect(department).toHaveValue("");
    expect(screen.queryByRole("option", { name: "Кадры" })).not.toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Терапия" })).toBeInTheDocument();
    await waitFor(() => expect(getPersonnelRoster).toHaveBeenLastCalledWith({ groupId: 1, orgUnitId: undefined }));
  });

  it("passes the same selected scope to preview and Excel", async () => {
    vi.mocked(getPersonnelReportOptions).mockResolvedValue(options);
    vi.mocked(getPersonnelRoster).mockResolvedValue(report);
    vi.mocked(downloadPersonnelRoster).mockResolvedValue();

    render(<PersonnelReportsPageClient />);
    const group = await screen.findByRole("combobox", { name: "Группа отделений" });
    const department = screen.getByRole("combobox", { name: "Отделение" });
    fireEvent.change(group, { target: { value: "1" } });
    fireEvent.change(department, { target: { value: "10" } });

    await waitFor(() => expect(getPersonnelRoster).toHaveBeenLastCalledWith({ groupId: 1, orgUnitId: 10 }));
    fireEvent.click(screen.getByRole("button", { name: "Скачать Excel" }));
    await waitFor(() => expect(downloadPersonnelRoster).toHaveBeenCalledWith({ groupId: 1, orgUnitId: 10 }));
  });

  it("shows a dedicated state when no groups or departments are accessible", async () => {
    vi.mocked(getPersonnelReportOptions).mockResolvedValue({ groups: [], departments: [] });

    render(<PersonnelReportsPageClient />);

    expect(await screen.findByText("Нет доступных групп или отделений.")).toBeInTheDocument();
    expect(getPersonnelRoster).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Скачать Excel" })).toBeDisabled();
  });
});
