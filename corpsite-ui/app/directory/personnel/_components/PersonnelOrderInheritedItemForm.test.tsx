import PersonnelOrderCreateDialog from "./PersonnelOrderCreateDialog";
import PersonnelOrderInheritedItemForm from "./PersonnelOrderInheritedItemForm";
import * as React from "react";
import {cleanup, fireEvent, render, screen, waitFor, within} from "@testing-library/react";
import {afterEach, beforeEach, expect, it, vi} from "vitest";
import PersonnelOrderItemEditor from "./PersonnelOrderItemEditor";
import {createPersonnelOrderItem, getPersonnelOrderAddItemContext, getPersonnelOrderPublishedVariants, getPersonnelOrderPublishedTemplateTitle, type PersonnelOrderDetailResponse} from "../_lib/personnelOrdersApi.client";
import {getEmployee, getEmployees} from "@/app/directory/employees/_lib/api.client";
import {personnelOrderTypeLabel} from "../_lib/personnelOrderLabels";
import {loadOrgUnitSelectOptions} from '@/lib/orgUnitsSelect';

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

it('inherits the preceding transfer unit and clears previous case corrections when switching employees',async()=>{
 const first={...template,template_id:6,template_version_id:50};const second={...template,template_id:30,template_version_id:49};
 vi.mocked(getPersonnelOrderAddItemContext).mockResolvedValue({available:true,item_type_code:'TRANSFER',template:first,default_employee_id:383,employee_ids:[383]});
 vi.mocked(getPersonnelOrderPublishedVariants).mockImplementation(async code=>({items:code==='TRANSFER'?[first]:code==='CONCURRENT_DUTY_START'?[second]:[],independent_supported:true,creation_supported:true}));
 vi.mocked(getPersonnelOrderPublishedTemplateTitle).mockImplementation(async(code,id)=>({template_version_id:id,item_type_code:code,title_ru:'О переводе',title_kk:'Ауыстыру туралы'}));
 vi.mocked(loadOrgUnitSelectOptions).mockResolvedValue([{...employee.org_unit,group_id:1}]);
 const item={item_id:1,order_id:77,item_number:1,item_type_code:'TRANSFER',item_status:'ACTIVE',employee_id:383,payload:{transfer:{org_unit_ru:employee.org_unit.name,org_unit_kk:employee.org_unit.name_kk,org_unit_id:59}}};
 render(<PersonnelOrderItemEditor orderId={77} orderTypeCode="TRANSFER" items={[item]} onChanged={vi.fn()}/>);toggle();
 await waitFor(()=>expect(screen.getByTestId('selected-employee-id')).toHaveValue('383'));
 await chooseNewItemType('CONCURRENT_DUTY_START');
 await waitFor(()=>expect(screen.getByLabelText('Дополнительное подразделение (KK)')).toHaveValue('Кір жуатын орынның'));
 expect(screen.getByLabelText('Дополнительное подразделение (RU)')).toHaveValue('Прачечная');
 expect(screen.getByTestId('personnel-order-create-blockers')).not.toHaveTextContent('Дополнительное подразделение');
 const gen=screen.getByLabelText('Дополнительное подразделение в родительном падеже (RU)');expect(gen).toHaveValue('прачечной');
 fireEvent.change(gen,{target:{value:'прачечной (уточнено)'}});
 fireEvent.click(screen.getByRole('button',{name:'Очистить сотрудника'}));
 const next={...employee,id:'384',fio:'Проверкин Иван Иванович'};
 vi.mocked(getEmployee).mockResolvedValue(next);vi.mocked(getEmployees).mockResolvedValue({items:[next],total:1});
 fireEvent.change(screen.getByLabelText('Сотрудник'),{target:{value:'Проверкин'}});fireEvent.click(await screen.findByRole('option',{name:next.fio}));
 await waitFor(()=>expect(screen.getByTestId('selected-employee-id')).toHaveValue('384'));
 expect(screen.getByLabelText('Дополнительное подразделение (RU)')).toHaveValue('');
 expect(screen.getByTestId('personnel-order-create-blockers')).toHaveTextContent('Дополнительное подразделение (RU)');
 expect(screen.getByLabelText('Дополнительное подразделение в родительном падеже (RU)')).toHaveValue('');
});

beforeEach(() => {
  vi.mocked(getPersonnelOrderPublishedTemplateTitle).mockImplementation(async(code,id)=>({template_version_id:id,item_type_code:code,title_ru:"Шаблон фикстуры",title_kk:"Сынақ үлгісі"}));
  vi.mocked(getPersonnelOrderAddItemContext).mockResolvedValue({available: true, item_type_code: "SUPPLEMENTARY_PAY", template, employee_ids: [1]});
  vi.mocked(getPersonnelOrderPublishedVariants).mockImplementation(async code => ({items: code === "SUPPLEMENTARY_PAY" ? [template] : [], independent_supported: true, creation_supported: true}));
  vi.mocked(getEmployees).mockResolvedValue({items: [employee], total: 1});
  vi.mocked(getEmployee).mockResolvedValue(employee);
  vi.mocked(createPersonnelOrderItem).mockResolvedValue(result);
});
afterEach(() => {cleanup(); vi.clearAllMocks();});

const disclosure = () => screen.getByTestId("personnel-order-add-item-disclosure") as HTMLDetailsElement;
const toggle = () => fireEvent.click(disclosure().querySelector("summary")!);

it.each([["ru", "личное заявление, трудовой договор"], ["kk", "жеке өтініші, еңбек шарты"]] as const)("defaults each new HIRE item using the saved %s document language and keeps edits", async (locale, basis) => {
  const hireTemplate = {...template, item_type_code: "HIRE"};
  const first = {item_id: 1, order_id: 77, item_number: 1, item_type_code: "HIRE", item_status: "ACTIVE", employee_id: null,
    payload: {new_employee: {last_name: "SYNTHETIC", first_name: "FIRST", middle_name: ""}, unresolved_subject: {full_name: "SYNTHETIC FIRST"}, employment_rate: 1, basis_other_text: "SAVED FIRST BASIS"}};
  vi.mocked(getPersonnelOrderAddItemContext).mockResolvedValue({available: true, item_type_code: "HIRE", source_title_locale: locale, template: hireTemplate, employee_ids: [], default_employee_id: null});
  vi.mocked(getPersonnelOrderPublishedVariants).mockImplementation(async code => ({items: code === "HIRE" ? [hireTemplate] : [], independent_supported: true, creation_supported: true}));
  vi.mocked(getPersonnelOrderPublishedTemplateTitle).mockResolvedValue({item_type_code: "HIRE", title_ru: "О приёме на работу", title_kk: "Жұмысқа қабылдау туралы"});
  vi.mocked(createPersonnelOrderItem).mockResolvedValue({...result, order: {...result.order, order_type_code: "HIRE"}, items: [first]});
  render(<PersonnelOrderItemEditor orderId={77} orderTypeCode="HIRE" items={[first]} onChanged={vi.fn()} />);
  toggle();
  const input = await screen.findByLabelText(`Основание (${locale.toUpperCase()})`, {selector: "textarea"});
  expect(input).toHaveValue(basis);
  fireEvent.change(input, {target: {value: "SYNTHETIC SECOND BASIS"}});
  toggle(); toggle();
  expect(screen.getByLabelText(`Основание (${locale.toUpperCase()})`, {selector: "textarea"})).toHaveValue("SYNTHETIC SECOND BASIS");
  expect(first.payload.basis_other_text).toBe("SAVED FIRST BASIS");
});

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
  fireEvent.change(screen.getByLabelText("Доплата"), {target: {value: percent === '35' ? 'other' : percent}});
  if (percent === '35') fireEvent.change(screen.getByLabelText('Процент доплаты'), {target:{value:percent}});
  await waitFor(() => expect(screen.getByRole("button", {name: "Добавить пункт"})).toBeEnabled());
}

it("offers published types and retains input across keyboard-compatible disclosure toggles", async () => {
  await setup();
  expect(screen.queryByLabelText("Тип пункта")).not.toBeInTheDocument();
  expect(screen.getByRole("button", {name: "Тип кадрового приказа"})).toBeInTheDocument();
  expect(screen.queryByLabelText("Номер приказа")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Ставка после перевода")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Замещаемый сотрудник")).not.toBeInTheDocument();
  expect(screen.getByLabelText("Основание (RU)")).toHaveValue("Личное заявление");
  expect(screen.getByLabelText("Основание (KK)")).toHaveValue("Жеке өтініш");
  expect(within(screen.getByLabelText("Доплата")).getAllByRole("option").map(option => option.textContent)).toEqual(["Выберите доплату", "+25%", "+50%", "Другое"]);
  expect(screen.getByRole("button", {name: "Добавить пункт"})).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Основание (RU)"), {target: {value: "Мой текст"}});
  const input = screen.getByLabelText("Сотрудник");
  fireEvent.change(input, {target: {value: "Введённый сотрудник"}});
  toggle(); expect(disclosure().open).toBe(false);
  toggle(); expect(screen.getByLabelText("Сотрудник")).toBe(input);
  expect(input).toHaveValue("Введённый сотрудник");
  expect(screen.getByLabelText("Основание (RU)")).toHaveValue("Мой текст");
  expect(getPersonnelOrderPublishedVariants).toHaveBeenCalled();
  expect(getPersonnelOrderPublishedTemplateTitle).toHaveBeenCalledWith("SUPPLEMENTARY_PAY",11);
});

it.each(["25", "35", "50"])("adds a second employee with numeric %s, then resets and collapses", async percent => {
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
  vi.mocked(getPersonnelOrderPublishedVariants).mockImplementation(async code => ({items: code === "CONCURRENT_DUTY_START" ? [{...template, template_id: mode === "RATE" ? 23 : 28, template_version_id: mode === "RATE" ? 38 : 44, replacement_mode: mode, replacement_optional_placement: mode === "PAY", service_area_allowance: mode === "PAY"}] : [], independent_supported: true}));
  render(<PersonnelOrderItemEditor orderId={77} items={[]} onChanged={vi.fn()} />); toggle();
  await screen.findByLabelText("Сотрудник");
  fireEvent.change(screen.getByLabelText("Сотрудник"), {target: {value: "Касымова"}});
  fireEvent.click(await screen.findByRole("option", {name: employee.fio}));
  if (mode === "RATE") await screen.findByLabelText("Дополнительная ставка");
  else await screen.findByLabelText("Доплата");
  expect(Boolean(screen.queryByLabelText("Дополнительная ставка"))).toBe(mode === "RATE");
  expect(Boolean(screen.queryByLabelText("Доплата"))).toBe(mode === "PAY");
  expect(getPersonnelOrderPublishedVariants).toHaveBeenCalled();
});

async function chooseNewItemType(code: string) {
  fireEvent.click(screen.getByRole("button", {name: "Тип кадрового приказа"}));
  fireEvent.change(screen.getByRole("searchbox"), {target: {value: personnelOrderTypeLabel(code, "kk")}});
  fireEvent.click(document.querySelector(`[data-type-code="${code}"]`)!);
}

it("adds work with allowance and total workload without inventing a rate or requiring replacement", async () => {
  const work = {...template, template_version_id: 123, replacement_mode: "WORK_ALLOWANCE" as const};
  vi.mocked(getPersonnelOrderAddItemContext).mockResolvedValue({available: true, item_type_code: "CONCURRENT_DUTY_START", template: work, employee_ids: [383], default_employee_id: 383});
  vi.mocked(getPersonnelOrderPublishedVariants).mockImplementation(async code => ({items: code === "CONCURRENT_DUTY_START" ? [work] : [], independent_supported: true, creation_supported: true}));
  render(<PersonnelOrderItemEditor orderId={77} orderTypeCode="CONCURRENT_DUTY_START" items={[]} onChanged={vi.fn()} />);
  toggle();
  await screen.findByLabelText("Процент доплаты");
  await waitFor(() => expect(screen.getByTestId("selected-employee-id")).toHaveValue("383"));
  expect(screen.queryByLabelText("Замещаемый сотрудник (RU)")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Срок замещения")).not.toBeInTheDocument();
  expect(screen.getByLabelText("Дополнительная ставка")).not.toBeRequired();
  const fields = {
    "Дата действия": "2026-02-02", "Дополнительная должность (RU)": "Врач-реабилитолог", "Дополнительная должность (KK)": "реабилитолог дәрігері",
    "Дополнительное подразделение (RU)": "Инсультный центр", "Дополнительное подразделение (KK)": "инсульт орталығының",
    "Дополнительная должность в родительном падеже (RU)": "врача-реабилитолога", "Дополнительное подразделение в родительном падеже (RU)": "инсультного центра",
    "ФИО в дательном падеже (RU)": "Тестовому Сотруднику", "ФИО в дательном падеже (KK)": "Сынақ Қызметкеріне",
    "Основание совмещения (RU)": "служебная записка", "Основание совмещения (KK)": "қызметтік хат",
    "Процент доплаты": "25", "База расчёта доплаты (RU)": "должностного оклада", "База расчёта доплаты (KK)": "лауазымдық айлық ақыдан", "Общая ставка": "1.25",
  };
  for(const [label,value] of Object.entries(fields))fireEvent.change(screen.getByLabelText(label), {target:{value}});
  expect(screen.getByLabelText("Дополнительная ставка")).toHaveValue(null);
  await waitFor(() => expect(screen.getByRole("button", {name:"Добавить пункт"})).toBeEnabled());
  fireEvent.click(screen.getByRole("button", {name:"Добавить пункт"}));
  await waitFor(() => expect(createPersonnelOrderItem).toHaveBeenCalled());
  const sent=vi.mocked(createPersonnelOrderItem).mock.calls[0][1];
  expect(sent).toMatchObject({item_type_code:"CONCURRENT_DUTY_START",template_version_id:123,effective_date:"2026-02-02",payload:{concurrent:{total_rate:1.25},replacement:{mode:"WORK_ALLOWANCE",allowance_percent:"25",allowance_basis_kk:"лауазымдық айлық ақыдан"}}});
  expect((sent.payload?.concurrent as Record<string,unknown>).rate).toBeUndefined();
  expect(sent.payload?.replacement).not.toHaveProperty("employee_id");
  expect(sent.payload?.replacement).not.toHaveProperty("term_type");
});

it("prefills the first employee and sends the selected new type and published version", async () => {
  const transfer = {...template, template_id: 10, template_version_id: 46, name_ru: "О переводе", name_kk: "Ауыстыру туралы"};
  vi.mocked(getPersonnelOrderAddItemContext).mockResolvedValue({available: true, item_type_code: "TRANSFER", template: transfer, employee_ids: [383], default_employee_id: 383});
  vi.mocked(getPersonnelOrderPublishedVariants).mockImplementation(async code => ({items: code === "TRANSFER" ? [transfer] : code === "SUPPLEMENTARY_PAY" ? [template, {...template, template_id: 7, template_version_id: 12, name_kk: "Екінші үлгі"}] : [], independent_supported: true}));
  const onChanged = vi.fn();
  render(<PersonnelOrderItemEditor orderId={77} orderTypeCode="TRANSFER" items={[]} onChanged={onChanged} />);
  toggle();
  await screen.findByLabelText(/Ставка после перевода/);
  await waitFor(() => expect(screen.getByTestId("selected-employee-id")).toHaveValue("383"));
  await chooseNewItemType("SUPPLEMENTARY_PAY");
  fireEvent.click(document.querySelector('[data-template-version="12"]')!);
  await screen.findByLabelText("Доплата");
  await waitFor(() => expect(screen.getByLabelText("Должность получателя (RU)")).toHaveValue(employee.position.name));
  expect(screen.queryByLabelText("Ставка после перевода")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Замещаемый сотрудник")).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Дата действия"), {target: {value: "2026-10-21"}});
  fireEvent.change(screen.getByLabelText("Доплата"), {target: {value: "25"}});
  await waitFor(() => expect(screen.getByRole("button", {name: "Добавить пункт"})).toBeEnabled());
  fireEvent.click(screen.getByRole("button", {name: "Добавить пункт"}));
  await waitFor(() => expect(createPersonnelOrderItem).toHaveBeenCalledWith(77, expect.objectContaining({employee_id: 383, item_type_code: "SUPPLEMENTARY_PAY", template_version_id: 12, payload: expect.objectContaining({allowance: expect.objectContaining({percent: 25})})})));
  expect(onChanged).toHaveBeenCalledWith(result);
});

it("blocks adding a type without a published version", async () => {
  await setup();
  await chooseNewItemType("TRANSFER");
  expect(screen.getByRole("button", {name: "Тип кадрового приказа"})).toHaveAttribute("value", "TRANSFER");
  expect(screen.getByRole("button", {name: "Добавить пункт"})).toBeDisabled();
  fireEvent.submit(screen.getByRole("button", {name: "Добавить пункт"}).closest("form")!);
  expect(createPersonnelOrderItem).not.toHaveBeenCalled();
});

it('keeps a cleared inherited employee cleared across context refresh and saves the explicitly chosen new person',async()=>{
 const second={...employee,id:'384',fio:'Акилтаева Тестовая Карточка',document_forms_ru:{employee_full_name_dative_ru:'Акилтаевой Тестовой Карточке'},document_forms_kk:{employee_full_name_dative_kk:'Акилтаеваға (сынақ)'}};
 vi.mocked(getPersonnelOrderAddItemContext).mockResolvedValue({available:true,item_type_code:'SUPPLEMENTARY_PAY',template,employee_ids:[383],default_employee_id:383});
 vi.mocked(getEmployee).mockImplementation(async id=>String(id)==='383'?employee:second);
 vi.mocked(getEmployees).mockResolvedValue({items:[second],total:1});
 const onAdded=vi.fn(),onCancel=vi.fn();const view=render(<PersonnelOrderInheritedItemForm orderId={77} orderItems={[]} onAdded={onAdded} onCancel={onCancel}/>);
 await waitFor(()=>expect(screen.getByTestId('selected-employee-id')).toHaveValue('383'));
 fireEvent.change(screen.getByLabelText('ФИО в дательном падеже (RU)'),{target:{value:'OLD_EMPLOYEE_FORM'}});
 fireEvent.click(screen.getByLabelText('Очистить сотрудника'));
 view.rerender(<PersonnelOrderInheritedItemForm orderId={77} orderItems={[]} onAdded={onAdded} onCancel={onCancel}/>);
 await waitFor(()=>expect(screen.queryByTestId('selected-employee-id')).not.toBeInTheDocument());
 expect(screen.getByLabelText('Сотрудник')).toHaveValue('');
 fireEvent.change(screen.getByLabelText('Сотрудник'),{target:{value:'Акилтаева'}});
 fireEvent.click(await screen.findByRole('option',{name:second.fio}));
 await waitFor(()=>expect(screen.getByTestId('selected-employee-id')).toHaveValue('384'));
 expect(screen.getByLabelText('ФИО в дательном падеже (RU)')).toHaveValue('Акилтаевой Тестовой Карточке');
 expect(screen.getByLabelText('ФИО в дательном падеже (KK)')).toHaveValue('Акилтаеваға (сынақ)');
 fireEvent.change(screen.getByLabelText('Дата действия'),{target:{value:'2026-10-25'}});
 fireEvent.change(screen.getByLabelText('Доплата'),{target:{value:'25'}});
 await waitFor(()=>expect(screen.getByRole('button',{name:'Добавить пункт'})).toBeEnabled());
 fireEvent.click(screen.getByRole('button',{name:'Добавить пункт'}));
 await waitFor(()=>expect(createPersonnelOrderItem).toHaveBeenCalledWith(77,expect.objectContaining({employee_id:384,payload:expect.objectContaining({allowance:expect.objectContaining({employee_dative_ru:'Акилтаевой Тестовой Карточке'})})})));
});


it("loads the exact inherited version instead of waiting forever on incomplete catalogue titles",async()=>{
  vi.mocked(getPersonnelOrderPublishedVariants).mockResolvedValue({items:[{...template,title_kk:""}],independent_supported:true,creation_supported:true});
  await setup(); await fill("25");
  expect(getPersonnelOrderPublishedTemplateTitle).toHaveBeenCalledWith("SUPPLEMENTARY_PAY",11);
  expect(screen.queryByTestId("selected-template-loading")).not.toBeInTheDocument();
  expect(screen.queryByTestId("selected-template-error")).not.toBeInTheDocument();
});

it("clears the loading state on an API error and retries the same selected version",async()=>{
  vi.mocked(getPersonnelOrderPublishedTemplateTitle).mockRejectedValueOnce(new Error("HTTP 503: temporary failure"));
  await setup();
  expect(await screen.findByTestId("selected-template-error")).toHaveTextContent("temporary failure");
  expect(screen.queryByTestId("selected-template-loading")).not.toBeInTheDocument();
  expect(screen.getByRole("button",{name:"Добавить пункт"})).toBeDisabled();
  fireEvent.click(screen.getByRole("button",{name:/Повторить загрузку шаблонов|Жүктеуді қайталау/}));
  await fill("25");
  expect(getPersonnelOrderPublishedTemplateTitle).toHaveBeenLastCalledWith("SUPPLEMENTARY_PAY",11);
  expect(screen.queryByTestId("selected-template-error")).not.toBeInTheDocument();
});

it("clears loading for a mismatched version and keeps Add disabled",async()=>{
  vi.mocked(getPersonnelOrderPublishedTemplateTitle).mockResolvedValue({template_version_id:999,item_type_code:"SUPPLEMENTARY_PAY",title_ru:"Other",title_kk:"Other"});
  await setup();
  expect(await screen.findByTestId("selected-template-error")).toHaveTextContent("не соответствует выбранной версии");
  expect(screen.queryByTestId("selected-template-loading")).not.toBeInTheDocument();
  expect(screen.getByRole("button",{name:"Добавить пункт"})).toBeDisabled();
});


it("retries the explicitly chosen version rather than resetting to the order's original version",async()=>{
  vi.mocked(getPersonnelOrderPublishedVariants).mockImplementation(async code=>({items:code==="SUPPLEMENTARY_PAY"?[template,{...template,template_version_id:12}]:[],independent_supported:true,creation_supported:true}));
  let failed=false;
  vi.mocked(getPersonnelOrderPublishedTemplateTitle).mockImplementation(async(code,id)=>{
    if(id===12&&!failed){failed=true;throw new Error("Retry chosen version");}
    return {template_version_id:id,item_type_code:code,title_ru:"Фикстура",title_kk:"Сынақ"};
  });
  await setup();await chooseNewItemType("SUPPLEMENTARY_PAY");fireEvent.click(document.querySelector('[data-template-version="12"]')!);
  expect(await screen.findByTestId("selected-template-error")).toHaveTextContent("Retry chosen version");
  fireEvent.click(screen.getByRole("button",{name:/Повторить загрузку шаблонов|Жүктеуді қайталау/}));
  await fill("25");
  expect(getPersonnelOrderPublishedTemplateTitle).toHaveBeenLastCalledWith("SUPPLEMENTARY_PAY",12);
});

it("reports an empty localized title as an error and clears loading",async()=>{
  vi.mocked(getPersonnelOrderPublishedTemplateTitle).mockResolvedValue({template_version_id:11,item_type_code:"SUPPLEMENTARY_PAY",title_ru:"Фикстура",title_kk:""});
  await setup();
  expect(await screen.findByTestId("selected-template-error")).toHaveTextContent("на выбранном языке");
  expect(screen.queryByTestId("selected-template-loading")).not.toBeInTheDocument();
  expect(screen.getByRole("button",{name:"Добавить пункт"})).toBeDisabled();
});


it("does not wait for an unrelated template catalogue after the selected type has loaded",async()=>{
  vi.mocked(getPersonnelOrderPublishedVariants).mockImplementation(code=>code==="HIRE"?new Promise(()=>{}):Promise.resolve({items:code==="SUPPLEMENTARY_PAY"?[template]:[],independent_supported:true,creation_supported:true}));
  await setup();await fill("25");
  expect(screen.getByRole("button",{name:"Добавить пункт"})).toBeEnabled();
  expect(getPersonnelOrderPublishedTemplateTitle).toHaveBeenCalledWith("SUPPLEMENTARY_PAY",11);
});


async function chooseManualSubject(){
  vi.mocked(getEmployees).mockResolvedValue({items:[],total:0});
  fireEvent.change(screen.getByLabelText("Сотрудник"),{target:{value:"Ручнова Тестовая Фикстура"}});
  fireEvent.click(await screen.findByRole("button",{name:"Использовать ФИО вручную"}));
  expect(screen.getByTestId("manual-subject-status")).toHaveTextContent("Карточка сотрудника не найдена");
  expect(screen.queryByTestId("selected-employee-id")).not.toBeInTheDocument();
}
function manualDepartmentFixture(){vi.mocked(loadOrgUnitSelectOptions).mockResolvedValue([{...employee.org_unit,group_id:1}]);}
async function fillManualAllowance(){
  fireEvent.change(screen.getByLabelText("Подразделение",{exact:true}),{target:{value:"59"}});
  fireEvent.change(screen.getByLabelText("Должность получателя (RU)"),{target:{value:"Врач"}});
  fireEvent.change(screen.getByLabelText("Должность получателя (KK)"),{target:{value:"дәрігері"}});
  fireEvent.change(screen.getByLabelText("ФИО в дательном падеже (RU)"),{target:{value:"Ручновой Тестовой Фикстуре"}});
  fireEvent.change(screen.getByLabelText("ФИО в дательном падеже (KK)"),{target:{value:"Қолмен енгізілген қызметкерге"}});
  fireEvent.change(screen.getByLabelText("Дата действия"),{target:{value:"2026-11-01"}});
  fireEvent.change(screen.getByLabelText("Доплата"),{target:{value:"25"}});
}
it("saves an explicitly manual subject without employee_id and still requires the other allowance fields",async()=>{
  manualDepartmentFixture();await setup();await chooseManualSubject();
  expect(screen.getByRole("button",{name:"Добавить пункт"})).toBeDisabled();
  await fillManualAllowance();
  const add=screen.getByRole("button",{name:"Добавить пункт"});await waitFor(()=>expect(add).toBeEnabled());fireEvent.click(add);
  await waitFor(()=>expect(createPersonnelOrderItem).toHaveBeenCalledWith(77,expect.objectContaining({employee_id:null,unresolved_subject:expect.objectContaining({full_name:"Ручнова Тестовая Фикстура"})})));
  expect(vi.mocked(createPersonnelOrderItem).mock.calls[0][1].payload).toMatchObject({allowance:{percent:25}});
});
it("creates the first order with a manual snapshot and no employee card",async()=>{
  manualDepartmentFixture();const created=vi.fn();
  const {createManualPersonnelOrderDraft,previewPersonnelOrderHeaderDuplicate}=await import("../_lib/personnelOrdersApi.client");
  const createManualSpy=vi.spyOn(await import("../_lib/personnelOrdersApi.client"),"createManualPersonnelOrderDraft").mockResolvedValue({order_id:91} as never);
  vi.spyOn(await import("../_lib/personnelOrdersApi.client"),"previewPersonnelOrderHeaderDuplicate").mockResolvedValue({blocking:false,candidates:[],warnings:[]} as never);
  render(<PersonnelOrderCreateDialog open onClose={vi.fn()} onCreated={created}/>);
  await chooseNewItemType("SUPPLEMENTARY_PAY");await chooseManualSubject();await fillManualAllowance();
  fireEvent.change(screen.getByLabelText("Номер приказа"),{target:{value:"MANUAL-FIXTURE"}});
  fireEvent.change(screen.getByLabelText("Дата приказа"),{target:{value:"2026-10-25"}});
  const add=screen.getByRole("button",{name:"Создать приказ"});await waitFor(()=>expect(add).toBeEnabled());fireEvent.click(add);
  await waitFor(()=>expect(createManualSpy).toHaveBeenCalledWith(expect.objectContaining({employee_id:null,unresolved_subject:expect.objectContaining({full_name:"Ручнова Тестовая Фикстура"})})));
});
it("replaces a manual subject with a selected directory employee and clears the manual marker",async()=>{
  manualDepartmentFixture();await setup();await chooseManualSubject();
  vi.mocked(getEmployees).mockResolvedValue({items:[employee],total:1});
  fireEvent.change(screen.getByLabelText("Сотрудник"),{target:{value:"Касымова"}});
  fireEvent.click(await screen.findByRole("option",{name:employee.fio}));
  await waitFor(()=>expect(screen.getByTestId("selected-employee-id")).toHaveValue("383"));
  expect(screen.queryByTestId("manual-subject-status")).not.toBeInTheDocument();
});
