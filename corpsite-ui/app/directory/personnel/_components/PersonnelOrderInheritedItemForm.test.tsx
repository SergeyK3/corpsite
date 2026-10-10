import * as React from "react";
import {cleanup, fireEvent, render, screen, waitFor, within} from "@testing-library/react";
import {afterEach, beforeEach, expect, it, vi} from "vitest";
import PersonnelOrderItemEditor from "./PersonnelOrderItemEditor";
import {createPersonnelOrderItem, getPersonnelOrderAddItemContext, getPersonnelOrderPublishedVariants, getPersonnelOrderPublishedTemplateTitle, type PersonnelOrderDetailResponse} from "../_lib/personnelOrdersApi.client";
import {getEmployee, getEmployees} from "@/app/directory/employees/_lib/api.client";

vi.mock("../_lib/personnelOrdersApi.client", async () => ({
  ...(await vi.importActual<object>("../_lib/personnelOrdersApi.client")),
  getPersonnelOrderAddItemContext: vi.fn(), createPersonnelOrderItem: vi.fn(),
  getPersonnelOrderPublishedVariants: vi.fn(), getPersonnelOrderPublishedTemplateTitle: vi.fn(),
}));
vi.mock("@/app/directory/employees/_lib/api.client", () => ({getEmployee: vi.fn(), getEmployees: vi.fn()}));
vi.mock("@/lib/orgUnitsSelect", () => ({loadOrgUnitSelectOptions: vi.fn().mockResolvedValue([])}));
vi.mock("@/lib/taskOrgFilters", async () => ({...(await vi.importActual<object>("@/lib/taskOrgFilters")), loadGlobalPositionCatalogCached: vi.fn().mockResolvedValue([]), loadScopedPositionOptions: vi.fn().mockResolvedValue([])}));
vi.mock("@/lib/orgScope", async () => ({...(await vi.importActual<object>("@/lib/orgScope")), fetchDepartmentGroups: vi.fn().mockResolvedValue([])}));

const template = {template_id: 6, template_version_id: 11, version_number: 1, name_ru: "О дополнительной оплате", name_kk: "Қосымша ақы туралы", title_ru: "О дополнительной оплате", title_kk: "Қосымша ақы туралы", is_default: false};
const employee = {id: "383", person_id: 720, fio: "Касымова Раушан Тастемировна", status: "active", department: null, rate: "1", date_from: null, date_to: null,
  active_assignment_id: 361, has_current_assignment: true,
  position: {id: 6, name: "Заведующая прачечной", name_kk: "кір жуатын орын меңгерушісі"},
  org_unit: {unit_id: 59, name: "Прачечная", name_kk: "Кір жуатын орын", document_genitive_kk: "Кір жуатын орынның", code: null, parent_unit_id: null, is_active: true}, assignments: []};
const result: PersonnelOrderDetailResponse = {order: {order_id: 77, order_type_code: "SUPPLEMENTARY_PAY", order_class: "SIMPLE", status: "DRAFT", source_mode: "MANUAL", created_by: 1}, items: [], localized_texts: [], attachments: [], prints: [], events: []};

beforeEach(() => {
  vi.mocked(getPersonnelOrderAddItemContext).mockResolvedValue({available: true, item_type_code: "SUPPLEMENTARY_PAY", template, employee_ids: [1]});
  vi.mocked(getEmployees).mockResolvedValue({items: [employee], total: 1});
  vi.mocked(getEmployee).mockResolvedValue(employee);
  vi.mocked(createPersonnelOrderItem).mockResolvedValue(result);
});
afterEach(() => {cleanup(); vi.clearAllMocks();});

const disclosure = () => screen.getByTestId("personnel-order-add-item-disclosure") as HTMLDetailsElement;
const toggle = () => fireEvent.click(disclosure().querySelector("summary")!);
async function setup() {
  const onChanged = vi.fn();
  render(<PersonnelOrderItemEditor orderId={77} orderTypeCode="SUPPLEMENTARY_PAY" items={[]} onChanged={onChanged} />);
  expect(disclosure().open).toBe(false);
  toggle();
  await screen.findByLabelText("Доплата");
  return onChanged;
}
async function fill(percent: string) {
  fireEvent.change(screen.getByLabelText("Сотрудник"), {target: {value: "Касымова"}});
  fireEvent.click(await screen.findByRole("option", {name: employee.fio}));
  await screen.findByTestId("allowance-recipient");
  fireEvent.change(screen.getByLabelText("Дата действия"), {target: {value: "2026-02-02"}});
  fireEvent.change(screen.getByLabelText("Доплата"), {target: {value: percent}});
  await waitFor(() => expect(screen.getByRole("button", {name: "Добавить пункт"})).toBeEnabled());
}

it("inherits the exact contract without a type menu or publication lookup, and retains input across keyboard-compatible disclosure toggles", async () => {
  await setup();
  expect(screen.queryByLabelText("Тип пункта")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Тип кадрового приказа")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Номер приказа")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Ставка после перевода")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Замещаемый сотрудник")).not.toBeInTheDocument();
  expect(screen.getByLabelText("Основание (RU)")).toHaveValue("Личное заявление");
  expect(screen.getByLabelText("Основание (KK)")).toHaveValue("Жеке өтініш");
  expect(within(screen.getByLabelText("Доплата")).getAllByRole("option").map(option => option.textContent)).toEqual(["Выберите доплату", "+25%", "+50%"]);
  expect(screen.getByRole("button", {name: "Добавить пункт"})).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Основание (RU)"), {target: {value: "Мой текст"}});
  const input = screen.getByLabelText("Сотрудник");
  fireEvent.change(input, {target: {value: "Введённый сотрудник"}});
  toggle(); expect(disclosure().open).toBe(false);
  toggle(); expect(screen.getByLabelText("Сотрудник")).toBe(input);
  expect(input).toHaveValue("Введённый сотрудник");
  expect(screen.getByLabelText("Основание (RU)")).toHaveValue("Мой текст");
  expect(getPersonnelOrderPublishedVariants).not.toHaveBeenCalled();
  expect(getPersonnelOrderPublishedTemplateTitle).not.toHaveBeenCalled();
});

it.each(["25", "50"])("adds a second employee with numeric %s, then resets and collapses", async percent => {
  const onChanged = await setup(); await fill(percent);
  fireEvent.change(screen.getByLabelText("Основание (KK)"), {target: {value: "Өз өтініші"}});
  fireEvent.click(screen.getByRole("button", {name: "Добавить пункт"}));
  await waitFor(() => expect(onChanged).toHaveBeenCalledWith(result));
  expect(createPersonnelOrderItem).toHaveBeenCalledWith(77, expect.objectContaining({template_version_id: 11, item_type_code: "SUPPLEMENTARY_PAY", employee_id: 383, effective_date: "2026-02-02", payload: expect.objectContaining({allowance: expect.objectContaining({percent: Number(percent), basis_ru: "Личное заявление", basis_kk: "Өз өтініші"})})}));
  expect(disclosure().open).toBe(false);
  toggle(); await screen.findByLabelText("Доплата");
  expect(screen.getByLabelText("Сотрудник")).toHaveValue("");
  expect(screen.getByLabelText("Доплата")).toHaveValue("");
  expect(screen.getByLabelText("Основание (KK)")).toHaveValue("Жеке өтініш");
});

it.each(['25', '50'])('adds without a KK position at %s and keeps optional manual refinements', async percent => {
  vi.mocked(getEmployee).mockResolvedValue({...employee, position: {id: 24, name: 'Машинист по стирке белья', name_kk: null}});
  const onChanged = await setup(); await fill(percent);
  expect(screen.getByLabelText('Должность получателя (KK)')).toHaveValue('');
  expect(screen.getByLabelText('Должность получателя в дательном падеже (RU)')).toHaveValue('машинисту по стирке белья');
  expect(screen.queryByTestId('personnel-order-text-forms')).not.toBeInTheDocument();
  expect(screen.queryByText(/Уточните поле «Должность получателя \(KK\)»/)).not.toBeInTheDocument();
  if (percent === '50') fireEvent.change(screen.getByLabelText('Должность получателя (KK)'), {target: {value: 'кір жуу машинисі'}});
  toggle(); toggle();
  expect(screen.getByLabelText('Должность получателя (KK)')).toHaveValue(percent === '50' ? 'кір жуу машинисі' : '');
  fireEvent.click(screen.getByRole('button', {name: 'Добавить пункт'}));
  await waitFor(() => expect(onChanged).toHaveBeenCalledWith(result));
  expect(createPersonnelOrderItem).toHaveBeenCalledWith(77, expect.objectContaining({template_version_id: 11, payload: expect.objectContaining({allowance_recipient: expect.objectContaining({position_kk: percent === '50' ? 'кір жуу машинисі' : ''})})}));
  expect(disclosure().open).toBe(false);
});

it("reopens after an in-flight error and retains fields and the error on subsequent toggles", async () => {
  let reject!: (reason: Error) => void;
  vi.mocked(createPersonnelOrderItem).mockImplementationOnce(() => new Promise((_, fail) => {reject = fail;}));
  const onChanged = await setup(); await fill("50");
  fireEvent.click(screen.getByRole("button", {name: "Добавить пункт"}));
  await waitFor(() => expect(createPersonnelOrderItem).toHaveBeenCalled());
  toggle(); expect(disclosure().open).toBe(false);
  reject(new Error("Ошибка сохранения"));
  await screen.findByText("Ошибка сохранения");
  expect(disclosure().open).toBe(true);
  expect(screen.getByLabelText("Доплата")).toHaveValue("50");
  expect(onChanged).not.toHaveBeenCalled();
  toggle(); toggle(); expect(screen.getByText("Ошибка сохранения")).toBeInTheDocument();
});

it.each(["Отсутствует привязка", "Противоречивые версии"])("blocks an unresolved contract: %s", async reason => {
  vi.mocked(getPersonnelOrderAddItemContext).mockResolvedValue({available: false, reason});
  render(<PersonnelOrderItemEditor orderId={77} items={[]} onChanged={vi.fn()} />); toggle();
  await screen.findByText(reason);
  expect(screen.queryByLabelText("Сотрудник")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", {name: "Добавить пункт"})).not.toBeInTheDocument();
});

it.each(["RATE", "PAY"] as const)("uses the pinned concurrent %s variant instead of another same-code publication", async mode => {
  vi.mocked(getPersonnelOrderAddItemContext).mockResolvedValue({available: true, employee_ids: [1], item_type_code: "CONCURRENT_DUTY_START", template: {...template, template_id: mode === "RATE" ? 23 : 28, template_version_id: mode === "RATE" ? 38 : 44, replacement_mode: mode, replacement_optional_placement: mode === "PAY", service_area_allowance: mode === "PAY"}});
  render(<PersonnelOrderItemEditor orderId={77} items={[]} onChanged={vi.fn()} />); toggle();
  await screen.findByLabelText("Сотрудник");
  fireEvent.change(screen.getByLabelText("Сотрудник"), {target: {value: "Касымова"}});
  fireEvent.click(await screen.findByRole("option", {name: employee.fio}));
  if (mode === "RATE") await screen.findByLabelText("Дополнительная ставка");
  else await screen.findByLabelText("Доплата");
  expect(Boolean(screen.queryByLabelText("Дополнительная ставка"))).toBe(mode === "RATE");
  expect(Boolean(screen.queryByLabelText("Доплата"))).toBe(mode === "PAY");
  expect(getPersonnelOrderPublishedVariants).not.toHaveBeenCalled();
});
