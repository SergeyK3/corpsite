import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PersonnelReportsPageClient from "./PersonnelReportsPageClient";
import {
  downloadPersonnelRoster,
  getPersonnelOrdersSummary,
  getPersonnelReportOptions,
  getPersonnelRoster,
  type PersonnelOrdersSummaryReport,
  type PersonnelRosterReport,
} from "../_lib/personnelReportsApi.client";

vi.mock("../_lib/personnelReportsApi.client", () => ({
  getPersonnelReportOptions: vi.fn(),
  getPersonnelRoster: vi.fn(),
  getPersonnelOrdersSummary: vi.fn(),
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

const ordersSummary: PersonnelOrdersSummaryReport = {
  report_code: "personnel_orders_summary",
  report_name: "Общая сводка по приказам",
  generated_at: "2026-08-29T09:30:00+00:00",
  filters: { date_from: null, date_to: null },
  period_note: null,
  categories: [
    {
      code: "hire",
      name: "Приём",
      count: 2,
      incomplete_count: 1,
      orders: [
        {
          order_id: 10,
          order_number: "10",
          order_date: "2026-06-10",
          order_type_code: "HIRE",
          item_type_codes: ["HIRE"],
          type_label: "Приём на работу",
          employee_names: ["Абдулов А.А.", "Бекова Б.Б."],
          department_names: ["Терапия"],
          status: "SIGNED",
          status_label: "Подписан",
          category_code: "hire",
        },
        {
          order_id: 11,
          order_number: "11",
          order_date: null,
          order_type_code: "HIRE",
          item_type_codes: ["HIRE"],
          type_label: "Приём на работу",
          employee_names: ["Без даты Б.Б."],
          department_names: ["Терапия"],
          status: "SIGNED",
          status_label: "Подписан",
          category_code: "hire",
        },
      ],
    },
    { code: "termination", name: "Увольнение", count: 0, incomplete_count: 0, orders: [] },
    { code: "transfer", name: "Перевод", count: 0, incomplete_count: 0, orders: [] },
    { code: "leave", name: "Отпуска", count: 0, incomplete_count: 0, orders: [] },
    { code: "other", name: "Прочие", count: 0, incomplete_count: 0, orders: [] },
  ],
  total_count: 2,
  total_incomplete_count: 1,
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

  it("keeps the personnel roster as the default report and opens the orders summary", async () => {
    vi.mocked(getPersonnelReportOptions).mockResolvedValue(options);
    vi.mocked(getPersonnelRoster).mockResolvedValue(report);
    vi.mocked(getPersonnelOrdersSummary).mockResolvedValue(ordersSummary);

    render(<PersonnelReportsPageClient />);

    expect(screen.getByRole("button", { name: /Личный состав/ })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: /Общая сводка по приказам/ }));

    await waitFor(() => expect(getPersonnelOrdersSummary).toHaveBeenCalledWith({ dateFrom: undefined, dateTo: undefined }));
    expect(screen.getByRole("button", { name: /Общая сводка по приказам/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("columnheader", { name: "В том числе без номера или даты" })).toBeInTheDocument();
    expect(screen.getByRole("rowheader", { name: "Всего" })).toBeInTheDocument();
  });

  it("starts categories collapsed and independently expands and collapses accessible details", async () => {
    vi.mocked(getPersonnelReportOptions).mockResolvedValue(options);
    vi.mocked(getPersonnelRoster).mockResolvedValue(report);
    vi.mocked(getPersonnelOrdersSummary).mockResolvedValue(ordersSummary);

    render(<PersonnelReportsPageClient />);
    fireEvent.click(screen.getByRole("button", { name: /Общая сводка по приказам/ }));

    const expandHire = await screen.findByRole("button", { name: "Раскрыть категорию Приём" });
    expect(expandHire).toHaveAttribute("aria-expanded", "false");
    expect(expandHire).toHaveAttribute("aria-controls", "orders-category-hire");
    expect(screen.queryByText("Абдулов А.А., Бекова Б.Б.")).not.toBeInTheDocument();

    fireEvent.click(expandHire);
    const collapseHire = screen.getByRole("button", { name: "Свернуть категорию Приём" });
    expect(collapseHire).toHaveAttribute("aria-expanded", "true");
    const datedOrderRow = screen.getByText("Абдулов А.А., Бекова Б.Б.").closest("tr");
    const undatedOrderRow = screen.getByText("Без даты Б.Б.").closest("tr");
    expect(datedOrderRow).not.toBeNull();
    expect(undatedOrderRow).not.toBeNull();
    expect(within(datedOrderRow!).getByText("10.06.2026")).toBeInTheDocument();
    expect(within(undatedOrderRow!).getByText("—")).toBeInTheDocument();
    expect(screen.getAllByText("Приём на работу")).toHaveLength(2);

    fireEvent.click(collapseHire);
    expect(screen.queryByText("Абдулов А.А., Бекова Б.Б.")).not.toBeInTheDocument();
  });

  it("shows an empty-category message and applies the official-date period", async () => {
    vi.mocked(getPersonnelReportOptions).mockResolvedValue(options);
    vi.mocked(getPersonnelRoster).mockResolvedValue(report);
    vi.mocked(getPersonnelOrdersSummary).mockResolvedValue(ordersSummary);

    render(<PersonnelReportsPageClient />);
    fireEvent.click(screen.getByRole("button", { name: /Общая сводка по приказам/ }));
    fireEvent.click(await screen.findByRole("button", { name: "Раскрыть категорию Увольнение" }));
    expect(screen.getByText("Приказы отсутствуют")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Дата с"), { target: { value: "2026-08-01" } });
    fireEvent.change(screen.getByLabelText("Дата по"), { target: { value: "2026-08-31" } });
    await waitFor(() =>
      expect(getPersonnelOrdersSummary).toHaveBeenLastCalledWith({
        dateFrom: "2026-08-01",
        dateTo: "2026-08-31",
      }),
    );
    expect(
      screen.getByText(/При заданном периоде приказы без официальной даты не включаются/),
    ).toBeInTheDocument();
  });
});
