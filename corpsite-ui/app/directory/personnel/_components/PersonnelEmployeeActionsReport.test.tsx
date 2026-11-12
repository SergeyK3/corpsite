import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import PersonnelEmployeeActionsReport from "./PersonnelEmployeeActionsReport";
import { getPersonnelEmployeeActionsReport } from "../_lib/personnelReportsApi.client";

vi.mock("../_lib/personnelReportsApi.client", () => ({ getPersonnelEmployeeActionsReport: vi.fn() }));

afterEach(() => { cleanup(); vi.clearAllMocks(); });

it("shows every active employee, filters by name, and expands counts from the same order rows", async () => {
  vi.mocked(getPersonnelEmployeeActionsReport).mockResolvedValue({
    report_code: "personnel_employee_actions",
    employees: [
      { employee_id: 1, full_name: "Без приказов", org_unit_id: 10, org_unit_name: "Терапия", order_count: 0, ordinary_order_count: 0, composite_order_count: 0, action_count: 0, actions_by_type: [], orders: [] },
      { employee_id: 2, full_name: "Иванова Мария", org_unit_id: 20, org_unit_name: "Хирургия", order_count: 2, ordinary_order_count: 1, composite_order_count: 1, action_count: 3,
        actions_by_type: [{ code: "HIRE", label: "Приём", count: 1 }, { code: "TRANSFER", label: "Перевод", count: 1 }, { code: "SUPPLEMENTARY_PAY", label: "Доплата", count: 1 }],
        orders: [
          { order_id: 12, order_number: "12", order_date: "2026-11-01", status: "SIGNED", status_label: "Подписан", is_composite: false, actions: [{ code: "HIRE", label: "Приём", count: 1 }] },
          { order_id: 13, order_number: "13", order_date: "2026-11-02", status: "REGISTERED", status_label: "Зарегистрирован", is_composite: true, actions: [{ code: "TRANSFER", label: "Перевод", count: 1 }, { code: "SUPPLEMENTARY_PAY", label: "Доплата", count: 1 }] },
        ] },
      { employee_id: 3, full_name: "Иванова Ольга", org_unit_id: 10, org_unit_name: "Терапия", order_count: 1, ordinary_order_count: 0, composite_order_count: 1, action_count: 1,
        actions_by_type: [{ code: "TRANSFER", label: "Перевод", count: 1 }],
        orders: [{ order_id: 13, order_number: "13", order_date: "2026-11-02", status: "REGISTERED", status_label: "Зарегистрирован", is_composite: true, actions: [{ code: "TRANSFER", label: "Перевод", count: 1 }] }] },
    ],
  });
  render(<PersonnelEmployeeActionsReport />);
  expect(await screen.findByRole("rowheader", { name: "Без приказов" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Приказы: Без приказов, 0" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Приказы: Иванова Мария, 2" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Кадровые действия: Иванова Мария, 3" })).toBeInTheDocument();
  expect(screen.getByRole("combobox", { name: "Подразделение" })).toHaveValue("");
  expect(screen.getByText("Обычные: 1 · Составные: 1")).toBeInTheDocument();
  expect(screen.getByText("Обычные: 0 · Составные: 1")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Кадровые действия: Иванова Мария, 3" }));
  const links = screen.getAllByRole("link");
  expect(links.map((link) => link.getAttribute("href"))).toEqual([
    "/directory/personnel/orders?order_id=12", "/directory/personnel/orders?order_id=13",
  ]);
  expect(within(screen.getByRole("rowheader", { name: "Иванова Мария" }).closest("tr")!).getByText(/Доплата: 1/)).toBeInTheDocument();
  expect(screen.getByText("Перевод: 1; Доплата: 1")).toBeInTheDocument();
  expect(screen.getByText("Составной")).toBeInTheDocument();
  fireEvent.change(screen.getByRole("searchbox", { name: "Поиск по ФИО" }), { target: { value: "иванова" } });
  expect(screen.queryByRole("rowheader", { name: "Без приказов" })).not.toBeInTheDocument();
  expect(screen.getByRole("rowheader", { name: "Иванова Мария" })).toBeInTheDocument();
  expect(screen.getByRole("rowheader", { name: "Иванова Ольга" })).toBeInTheDocument();
  fireEvent.change(screen.getByRole("combobox", { name: "Подразделение" }), { target: { value: "20" } });
  expect(screen.getByRole("rowheader", { name: "Иванова Мария" })).toBeInTheDocument();
  expect(screen.queryByRole("rowheader", { name: "Иванова Ольга" })).not.toBeInTheDocument();
  fireEvent.change(screen.getByRole("searchbox", { name: "Поиск по ФИО" }), { target: { value: "без" } });
  expect(screen.queryByRole("rowheader", { name: "Без приказов" })).not.toBeInTheDocument();
  fireEvent.change(screen.getByRole("combobox", { name: "Подразделение" }), { target: { value: "10" } });
  expect(screen.getByRole("rowheader", { name: "Без приказов" })).toBeInTheDocument();
});

it("refreshes an already open report after a composite order is registered", async () => {
  const hire = { order_id: 10, order_number: "10", order_date: "2025-09-18", status: "SIGNED" as const,
    status_label: "Подписан", is_composite: false,
    actions: [{ code: "HIRE", label: "Приём на работу", count: 1 }] };
  const composite = { order_id: 5649, order_number: "48 тест", order_date: "2026-01-12", status: "REGISTERED" as const,
    status_label: "Зарегистрирован", is_composite: true,
    actions: [{ code: "TRANSFER", label: "Перевод", count: 1 },
      { code: "CONCURRENT_DUTY_START", label: "Начало совмещения", count: 1 }] };
  const base = { employee_id: 391, full_name: "Искакова Сымбат Мылтыкпаевна",
    org_unit_id: 65, org_unit_name: "ЦСО" };
  vi.mocked(getPersonnelEmployeeActionsReport)
    .mockResolvedValueOnce({ report_code: "personnel_employee_actions", employees: [{ ...base,
      order_count: 1, ordinary_order_count: 1, composite_order_count: 0, action_count: 1,
      actions_by_type: hire.actions, orders: [hire] }] })
    .mockResolvedValueOnce({ report_code: "personnel_employee_actions", employees: [{ ...base,
      order_count: 2, ordinary_order_count: 1, composite_order_count: 1, action_count: 3,
      actions_by_type: [...hire.actions, ...composite.actions], orders: [composite, hire] }] })
    .mockResolvedValueOnce({ report_code: "personnel_employee_actions", employees: [{ ...base,
      order_count: 2, ordinary_order_count: 1, composite_order_count: 1, action_count: 3,
      actions_by_type: [...hire.actions, ...composite.actions], orders: [composite, hire] }] });

  render(<PersonnelEmployeeActionsReport />);
  expect(await screen.findByRole("button", { name: "Приказы: Искакова Сымбат Мылтыкпаевна, 1" })).toBeInTheDocument();
  await new Promise((resolve) => setTimeout(resolve, 550));
  fireEvent.focus(window);
  expect(await screen.findByRole("button", { name: "Приказы: Искакова Сымбат Мылтыкпаевна, 2" })).toBeInTheDocument();
  expect(screen.getByText("Обычные: 1 · Составные: 1")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Кадровые действия: Искакова Сымбат Мылтыкпаевна, 3" })).toBeInTheDocument();
  expect(getPersonnelEmployeeActionsReport).toHaveBeenCalledTimes(2);
  fireEvent.click(screen.getByRole("button", { name: "Обновить отчёт" }));
  expect(getPersonnelEmployeeActionsReport).toHaveBeenCalledTimes(3);
});
