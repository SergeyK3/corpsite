import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import PersonnelOrderCreateDialog from "./PersonnelOrderCreateDialog";

vi.mock("../_lib/personnelOrdersApi.client", async () => {
  const actual = await vi.importActual<typeof import("../_lib/personnelOrdersApi.client")>("../_lib/personnelOrdersApi.client");
  return { ...actual, previewPersonnelOrderHeaderDuplicate: vi.fn(), createManualPersonnelOrderDraft: vi.fn() };
});
vi.mock("@/app/directory/employees/_lib/api.client", () => ({ getEmployee: vi.fn(), getEmployees: vi.fn() }));
import { createManualPersonnelOrderDraft, previewPersonnelOrderHeaderDuplicate } from "../_lib/personnelOrdersApi.client";
import { getEmployee, getEmployees } from "@/app/directory/employees/_lib/api.client";

afterEach(() => { cleanup(); vi.clearAllMocks(); });
const testEmployee = { id: "7", fio: "Тестова Анна", position: { id: 2, name: "невролог" }, org_unit: { unit_id: 3, name: "инсультный центр", code: null, parent_unit_id: null, is_active: true }, department: null, rate: null, status: "active", date_from: null, date_to: null };
function fillWithoutEmployee() { fireEvent.change(screen.getByLabelText("Номер приказа"), { target: { value: "M-1" } }); fireEvent.change(screen.getByLabelText("Дата приказа"), { target: { value: "2026-09-25" } }); fireEvent.change(screen.getByLabelText("Исходное название"), { target: { value: "Атауы" } }); fireEvent.change(screen.getByLabelText("Дата действия"), { target: { value: "2026-10-01" } }); }
async function selectTestEmployee() { vi.mocked(getEmployees).mockResolvedValue({ items: [testEmployee], total: 1 }); fireEvent.change(screen.getByLabelText("Сотрудник"), { target: { value: "Тест" } }); expect(await screen.findByText("Тестова Анна")).toBeInTheDocument(); expect(screen.getByText("невролог · инсультный центр")).toBeInTheDocument(); fireEvent.click(screen.getByRole("option", { name: /Тестова Анна/ })); expect(screen.getByLabelText("Сотрудник")).toHaveValue("Тестова Анна"); expect(screen.getByLabelText("Должность в приказе")).toHaveValue("невролог"); expect(screen.getByLabelText("Отделение в приказе")).toHaveValue("инсультный центр"); }

it("validates fields, previews duplicates, confirms warning, and opens the created order", async () => {
  vi.mocked(previewPersonnelOrderHeaderDuplicate).mockResolvedValue({ blocking: false, warnings: ["SAME_NUMBER_DIFFERENT_DATE"], candidates: [] });
  vi.mocked(createManualPersonnelOrderDraft).mockResolvedValue({ order_id: 77, order_number: "M-1", order_type_code: "HIRE", status: "DRAFT", source_mode: "MANUAL", document_revision: 1, document_review_state: "NEEDS_REVIEW" });
  const onCreated = vi.fn(); const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
  render(<PersonnelOrderCreateDialog open onClose={vi.fn()} onCreated={onCreated} />);
  expect(screen.getByTestId("personnel-order-create-dialog")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Создать приказ" }));
  expect(createManualPersonnelOrderDraft).not.toHaveBeenCalled();
  fillWithoutEmployee(); await selectTestEmployee(); fireEvent.change(screen.getByLabelText("Должность в приказе"), { target: { value: "врач (ординатор)" } }); fireEvent.change(screen.getByLabelText("Отделение в приказе"), { target: { value: "Инсультный центр" } }); fireEvent.change(screen.getByLabelText("Специальность"), { target: { value: "невропатолог" } }); fireEvent.click(screen.getByRole("button", { name: "Создать приказ" }));
  await waitFor(() => expect(previewPersonnelOrderHeaderDuplicate).toHaveBeenCalled());
  await waitFor(() => expect(confirm).toHaveBeenCalled());
  await waitFor(() => expect(createManualPersonnelOrderDraft).toHaveBeenCalledWith(expect.objectContaining({ order_number: "M-1", employee_id: 7, effective_date: "2026-10-01", document_subject_context: { position_name: "врач (ординатор)", org_unit_name: "Инсультный центр", specialty: "невропатолог" } })));
  expect(onCreated).toHaveBeenCalledWith(expect.objectContaining({ order_id: 77 })); confirm.mockRestore();
});

it("blocks save when duplicate preview is blocking", async () => {
  vi.mocked(previewPersonnelOrderHeaderDuplicate).mockResolvedValue({ blocking: true, warnings: [], candidates: [] });
  render(<PersonnelOrderCreateDialog open onClose={vi.fn()} onCreated={vi.fn()} />); fillWithoutEmployee(); await selectTestEmployee(); fireEvent.click(screen.getByRole("button", { name: "Создать приказ" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("таким же номером и датой"); expect(createManualPersonnelOrderDraft).not.toHaveBeenCalled();
});

it("requires a directory selection and clears it without accepting an arbitrary id", async () => {
  render(<PersonnelOrderCreateDialog open onClose={vi.fn()} onCreated={vi.fn()} />);
  fillWithoutEmployee();
  fireEvent.change(screen.getByLabelText("Сотрудник"), { target: { value: "7" } });
  fireEvent.click(screen.getByRole("button", { name: "Создать приказ" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Выберите сотрудника из списка");
  expect(previewPersonnelOrderHeaderDuplicate).not.toHaveBeenCalled();
  await selectTestEmployee();
  expect(screen.getByLabelText("Сотрудник")).toHaveValue("Тестова Анна");
  fireEvent.click(screen.getByRole("button", { name: "Очистить выбранного сотрудника" }));
  expect(screen.getByLabelText("Сотрудник")).toHaveValue("");
});

it("creates an unlinked typed subject when the directory search has no result", async () => {
  vi.mocked(getEmployees).mockResolvedValue({ items: [], total: 0 });
  vi.mocked(previewPersonnelOrderHeaderDuplicate).mockResolvedValue({ blocking: false, warnings: [], candidates: [] });
  vi.mocked(createManualPersonnelOrderDraft).mockResolvedValue({ order_id: 78, order_number: "M-1", order_type_code: "HIRE", status: "DRAFT", source_mode: "MANUAL", document_revision: 1, document_review_state: "NEEDS_REVIEW" });
  render(<PersonnelOrderCreateDialog open onClose={vi.fn()} onCreated={vi.fn()} />);
  fireEvent.change(screen.getByLabelText("Сотрудник"), { target: { value: "Тест" } });
  expect(await screen.findByText("Сотрудники не найдены.")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Указать сотрудника вручную" }));
  fireEvent.change(screen.getByLabelText("ФИО вручную"), { target: { value: "Тестова Анна" } });
  fireEvent.change(screen.getByLabelText("Отделение вручную"), { target: { value: "Инсультный центр" } });
  fireEvent.change(screen.getByLabelText("Должность вручную"), { target: { value: "врач (ординатор)" } });
  fireEvent.change(screen.getByLabelText("Специальность вручную"), { target: { value: "невропатолог" } });
  fillWithoutEmployee();
  fireEvent.change(screen.getByLabelText("Язык исходного названия"), { target: { value: "ru" } });
  fireEvent.change(screen.getByLabelText("Тип пункта"), { target: { value: "TRANSFER" } });
  expect(screen.getByLabelText("ФИО вручную")).toHaveValue("Тестова Анна");
  expect(screen.getByLabelText("Отделение вручную")).toHaveValue("Инсультный центр");
  expect(screen.getByLabelText("Должность вручную")).toHaveValue("врач (ординатор)");
  expect(screen.getByLabelText("Специальность вручную")).toHaveValue("невропатолог");
  fireEvent.click(screen.getByRole("button", { name: "Создать приказ" }));
  await waitFor(() => expect(createManualPersonnelOrderDraft).toHaveBeenCalledWith(expect.objectContaining({ order_number: "M-1", order_date: "2026-09-25", source_title: "Атауы", source_title_locale: "ru", item_type_code: "TRANSFER", effective_date: "2026-10-01", employee_id: null, unresolved_subject: { full_name: "Тестова Анна", org_unit_name: "Инсультный центр", position_name: "врач (ординатор)", specialty: "невропатолог" } })));
  expect(JSON.stringify(vi.mocked(createManualPersonnelOrderDraft).mock.calls[0][0])).not.toContain("payload");
});

it("prefills the unique scoped employee found from the page filter", async () => {
  const scopedEmployee = { ...testEmployee, id: "42", fio: "Тестовый сотрудник", position: { id: 4, name: "Тестовая должность" }, org_unit: { ...testEmployee.org_unit!, name: "Тестовое отделение" }, specialty: "Тестовая специальность" } as typeof testEmployee & { specialty: string };
  vi.mocked(getEmployees).mockResolvedValue({ items: [scopedEmployee], total: 1 });
  render(<PersonnelOrderCreateDialog open initialEmployeeQuery="Тестовый" onClose={vi.fn()} onCreated={vi.fn()} />);
  await waitFor(() => expect(screen.getByLabelText("Сотрудник")).toHaveValue("Тестовый сотрудник"));
  expect(screen.getByLabelText("Должность в приказе")).toHaveValue("Тестовая должность");
  expect(screen.getByLabelText("Отделение в приказе")).toHaveValue("Тестовое отделение");
  expect(screen.getByLabelText("Специальность")).toHaveValue("Тестовая специальность");
});

it("uses the exact employee id from the filter before considering its text query", async () => {
  vi.mocked(getEmployee).mockResolvedValue({ ...testEmployee, id: "42", fio: "Тестовый сотрудник" });
  render(<PersonnelOrderCreateDialog open initialEmployeeId={42} initialEmployeeQuery="другой текст" onClose={vi.fn()} onCreated={vi.fn()} />);
  await waitFor(() => expect(screen.getByLabelText("Сотрудник")).toHaveValue("Тестовый сотрудник"));
  expect(getEmployee).toHaveBeenCalledWith("42");
  expect(getEmployees).not.toHaveBeenCalled();
});

it("does not auto-select an ambiguous text filter", async () => {
  vi.mocked(getEmployees).mockResolvedValue({ items: [testEmployee, { ...testEmployee, id: "8", fio: "Тестова Анна Вторая" }], total: 2 });
  render(<PersonnelOrderCreateDialog open initialEmployeeQuery="Тестова" onClose={vi.fn()} onCreated={vi.fn()} />);
  expect(await screen.findAllByRole("option", { name: /Тестова Анна/ })).toHaveLength(2);
  expect(screen.getByLabelText("Сотрудник")).toHaveValue("Тестова");
  expect(screen.queryByLabelText("Должность в приказе")).not.toBeInTheDocument();
});

it("keeps create and cancel in the fixed dialog footer", () => {
  render(<PersonnelOrderCreateDialog open onClose={vi.fn()} onCreated={vi.fn()} />);
  const footer = screen.getByTestId("personnel-order-create-footer");
  expect(footer).toContainElement(screen.getByRole("button", { name: "Отмена" }));
  expect(footer).toContainElement(screen.getByRole("button", { name: "Создать приказ" }));
});
