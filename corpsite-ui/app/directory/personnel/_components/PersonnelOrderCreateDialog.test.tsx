import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import PersonnelOrderCreateDialog from "./PersonnelOrderCreateDialog";

it("prefills recall from a selected Musabekov, keeps corrections, and uses manual case input when missing", async () => {
  setup();
  const musabekov={...employeeDetail,id:"77",fio:"Мусабеков Арман Ерланович",has_current_assignment:true,
    position:{id:6,name:"Врач",job_nameru:"врач",job_namekk:"дәрігер"},
    org_unit:{...employeeDetail.org_unit,name:"Терапия",name_kk:"Терапия"}};
  vi.mocked(getEmployees).mockResolvedValue({items:[musabekov,musabekov],total:2});vi.mocked(getEmployee).mockResolvedValue(musabekov);
  await chooseTypeInMenu("LEAVE.ANNUAL.RECALL");fireEvent.change(screen.getByLabelText("Сотрудник"),{target:{value:"Мусабеков"}});
  const option=await screen.findByRole("option",{name:/Мусабеков Арман Ерланович/});expect(option).toHaveTextContent("Терапия");
  expect(screen.getAllByRole("option",{name:/Мусабеков Арман Ерланович/})).toHaveLength(1);fireEvent.click(option);
  await waitFor(()=>expect(screen.getByTestId("selected-employee-id")).toHaveValue("77"));
  expect(screen.getByLabelText("Должность")).toHaveValue("врач");expect(screen.getByLabelText("Лауазым KZ")).toHaveValue("дәрігер");
  expect(screen.getByLabelText("Подразделение")).toHaveValue("Терапия");expect(screen.getByLabelText("Бөлімше KZ")).toHaveValue("Терапия");
  expect(screen.getByLabelText("Основание RU")).toHaveValue("Докладная записка и личное согласие Мусабекова Армана Ерлановича");
  expect(screen.getByLabelText("Негіз KZ")).toHaveValue("Баяндау хат және Арман Ерланович Мусабековтің жеке келісімі");
  fireEvent.change(screen.getByLabelText("Основание RU"),{target:{value:"Ручное основание"}});
  fireEvent.change(screen.getByLabelText("ФИО в родительном падеже (RU)"),{target:{value:"Ручная форма ФИО"}});
  expect(screen.getByLabelText("Основание RU")).toHaveValue("Ручное основание");
  fireEvent.click(screen.getByRole("button",{name:"Негізді ұсыну RU"}));
  expect(screen.getByLabelText("Основание RU")).toHaveValue("Докладная записка и личное согласие Ручная форма ФИО");
  fireEvent.click(screen.getByRole("button",{name:"Сменить сотрудника"}));
  const unknown={...musabekov,id:"78",fio:"Неизвестный"};vi.mocked(getEmployees).mockResolvedValue({items:[unknown],total:1});vi.mocked(getEmployee).mockResolvedValue(unknown);
  fireEvent.change(screen.getByLabelText("Сотрудник"),{target:{value:"Неизвестный"}});fireEvent.click(await screen.findByRole("option",{name:/Неизвестный/}));
  await waitFor(()=>expect(screen.getByTestId("selected-employee-id")).toHaveValue("78"));
  expect(screen.getByLabelText("Основание RU")).toHaveValue("");expect(screen.getByLabelText("Негіз KZ")).toHaveValue("");
  fireEvent.change(screen.getByLabelText("ФИО в родительном падеже (RU)"),{target:{value:"Сотрудника"}});
  expect(screen.getByLabelText("Основание RU")).toHaveValue("Докладная записка и личное согласие Сотрудника");
});

it("allows an explicit document position for recall when the test employee has no current assignment", async () => {
  setup();vi.mocked(getEmployee).mockResolvedValue({...employeeDetail,active_assignment_id:null,has_current_assignment:false} as never);
  await chooseTypeInMenu("LEAVE.ANNUAL.RECALL");await selectEmployee();
  const position=screen.getByLabelText("Должность");expect(position).toHaveValue("");
  fireEvent.change(position,{target:{value:"врач"}});expect(position).toHaveValue("врач");
  expect(createManualPersonnelOrderDraft).not.toHaveBeenCalled();
});

it("creates a recall with separate bilingual bases and no rate or leave period", async () => {
  setup(); await chooseTypeInMenu("LEAVE.ANNUAL.RECALL"); await selectEmployee();
  fireEvent.change(screen.getByLabelText("Номер приказа"), {target:{value:"RECALL-TEST"}});
  fireEvent.change(screen.getByLabelText("Дата приказа"), {target:{value:"2026-10-07"}});
  fireEvent.change(screen.getByLabelText("Дата действия"), {target:{value:"2026-10-12"}});
  expect(screen.getByRole("button",{name:"Создать приказ"})).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Лауазым KZ"), {target:{value:"дәрігер"}});
  fireEvent.change(screen.getByLabelText("Бөлімше KZ"), {target:{value:"Терапия"}});
  fireEvent.change(screen.getByLabelText("Основание RU"), {target:{value:"Служебная записка"}});
  fireEvent.change(screen.getByLabelText("Негіз KZ"), {target:{value:"Қызметтік хат"}});
  vi.mocked(previewPersonnelOrderHeaderDuplicate).mockResolvedValue({blocking:false,warnings:[],candidates:[]});
  vi.mocked(createManualPersonnelOrderDraft).mockResolvedValue({order_id:1} as never);
  await waitFor(() => expect(screen.getByRole("button",{name:"Создать приказ"})).toBeEnabled());
  fireEvent.click(screen.getByRole("button",{name:"Создать приказ"}));
  await waitFor(() => expect(createManualPersonnelOrderDraft).toHaveBeenCalledWith(expect.objectContaining({item_type_code:"LEAVE.ANNUAL.RECALL",effective_date:"2026-10-12",period_start:null,period_end:null,item_payload:expect.objectContaining({recall_position_kk:"дәрігер",recall_org_unit_kk:"Терапия",basis_ru:"Служебная записка",basis_kk:"Қызметтік хат"})})));
});
import { personnelOrderTypeLabel } from "../_lib/personnelOrderLabels";

vi.mock("../_lib/personnelOrdersApi.client", async () => ({
  ...(await vi.importActual<object>("../_lib/personnelOrdersApi.client")),
  getPersonnelOrderPublishedTemplateTitle: vi.fn(),
  getPersonnelOrderPublishedVariants: vi.fn().mockResolvedValue({ items: [], independent_supported: false }),
  previewPersonnelOrderHeaderDuplicate: vi.fn(),
  createManualPersonnelOrderDraft: vi.fn(),
}));
vi.mock("@/app/directory/employees/_lib/api.client", () => ({ getEmployee: vi.fn(), getEmployees: vi.fn(), getPositions: vi.fn().mockResolvedValue({items:[],total:0}) }));
vi.mock("@/lib/orgUnitsSelect", () => ({ loadOrgUnitSelectOptions: vi.fn() }));

import {
  PERSONNEL_ORDER_CREATE_TYPE_OPTIONS,
  getPersonnelOrderPublishedVariants,
  createManualPersonnelOrderDraft,
  getPersonnelOrderPublishedTemplateTitle,
  previewPersonnelOrderHeaderDuplicate,
} from "../_lib/personnelOrdersApi.client";
import { getEmployee, getEmployees } from "@/app/directory/employees/_lib/api.client";
import { loadOrgUnitSelectOptions } from "@/lib/orgUnitsSelect";

// Actual /directory/employees search item and /directory/employees/383 detail.
const employee = {
  id: "383",
  person_id: 720,
  fio: "Ильясова Ассель Адиловна",
  position: { id: 6, name: "Врач", name_kk: "дәрігер" },
  org_unit: { unit_id: 59, name: "Лучевая диагностика", code: "DIAG_IMG", parent_unit_id: 41, is_active: true },
  department: null,
  rate: "1.0",
  status: "active",
  date_from: "2026-05-15",
  date_to: null,
  termination: null,
  source: { relation: "employees" },
};
const employeeDetail = {
  ...employee,
  active_assignment_id: 361,
  org_unit: { ...employee.org_unit, document_genitive_kk: "Сәулелік диагностика бөлімшесінің" },
  user: null,
};

const unpaidTitles = {
  item_type_code: "LEAVE.UNPAID.GRANT",
  title_kk: "Еңбекақысы сақталмайтын демалыс туралы",
  title_ru: "О предоставлении отпуска без сохранения заработной платы",
};
const transferTitles = {
  item_type_code: "TRANSFER",
  title_kk: "Басқа лауазымға ауыстыру туралы",
  title_ru: "О переводе на другую должность",
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.mocked(getPersonnelOrderPublishedVariants).mockReset().mockResolvedValue({items:[],independent_supported:false});
});

it("shows variant load errors and blocks creation instead of silently falling back",async()=>{
  vi.mocked(getPersonnelOrderPublishedVariants).mockRejectedValue(new Error('Schema unavailable'));
  setup();
  expect(screen.getByRole('button',{name:'Тип кадрового приказа'})).toBeEnabled();
  await chooseTypeInMenu('LEAVE.ANNUAL.GRANT');await selectEmployee();
  fireEvent.change(screen.getByLabelText('Номер приказа'),{target:{value:'LEGACY-UNIT'}});
  fireEvent.change(screen.getByLabelText('Дата приказа'),{target:{value:'2026-10-07'}});
  fireEvent.change(screen.getByLabelText('Дата действия'),{target:{value:'2026-10-12'}});
  expect(await screen.findByRole('alert')).toHaveTextContent('Schema unavailable');
  expect(screen.getByRole('button',{name:'Создать приказ'})).toBeDisabled();
  fireEvent.submit(screen.getByRole('button',{name:'Создать приказ'}).closest('form')!);
  expect(previewPersonnelOrderHeaderDuplicate).not.toHaveBeenCalled();
  expect(createManualPersonnelOrderDraft).not.toHaveBeenCalled();
  vi.mocked(getPersonnelOrderPublishedVariants).mockResolvedValue({items:[],independent_supported:false});
  fireEvent.click(screen.getByRole('button',{name:'Жүктеуді қайталау'}));
  await waitFor(()=>expect(screen.getByRole('button',{name:'Создать приказ'})).toBeEnabled());
});

it("allows recall selection but blocks its creation when the actual schema does not allow the code",async()=>{
  vi.mocked(getPersonnelOrderPublishedVariants).mockImplementation(async code=>({items:[],independent_supported:false,creation_supported:code!=='LEAVE.ANNUAL.RECALL',creation_reason:code==='LEAVE.ANNUAL.RECALL'?'Requires hrrecall001':null}));
  setup();await chooseTypeInMenu('LEAVE.ANNUAL.RECALL');
  await screen.findByTestId('order-type-schema-unavailable');
  expect(screen.getByTestId('order-type-schema-unavailable')).toHaveTextContent('hrrecall001');
  expect(screen.getByRole('button',{name:'Создать приказ'})).toBeDisabled();
  expect(screen.getByRole('button',{name:'Тип кадрового приказа'})).toBeEnabled();
  await chooseTypeInMenu('LEAVE.ANNUAL.GRANT');
  expect(screen.queryByTestId('order-type-schema-unavailable')).not.toBeInTheDocument();
});

function setup(onClose: () => void = vi.fn(), onCreated: (order: Awaited<ReturnType<typeof createManualPersonnelOrderDraft>>) => void = vi.fn()) {
  vi.mocked(getPersonnelOrderPublishedTemplateTitle).mockImplementation(async (type) =>
    type === "TRANSFER" ? transferTitles : unpaidTitles,
  );
  vi.mocked(getEmployees).mockResolvedValue({ items: [employee], total: 1 });
  vi.mocked(getEmployee).mockResolvedValue(employeeDetail);
  vi.mocked(loadOrgUnitSelectOptions).mockResolvedValue([
    { unit_id: 41, name: "Многопрофильный медицинский центр", group_id: null, name_kk: null, document_genitive_kk: null },
    { unit_id: 59, name: "Лучевая диагностика", group_id: 2, name_kk: "Сәулелік диагностика бөлімшесі", document_genitive_kk: "Сәулелік диагностика бөлімшесінің" },
  ]);
  const view = render(<PersonnelOrderCreateDialog open onClose={onClose} onCreated={onCreated} />);
  return { onClose, onCreated, ...view };
}

const recallVariant = {template_id:8,template_version_id:13,version_number:1,name_ru:"Об отзыве из отпуска",name_kk:"Еңбек демалысынан шақырту туралы",title_ru:"Об отзыве из отпуска",title_kk:"Еңбек демалысынан шақырту туралы",is_default:false};

async function fillRecall(select = true) {
  if (select) await selectEmployee();
  for (const [label,value] of [["Номер приказа","RECALL-SLOW"],["Дата приказа","2026-10-08"],["Дата действия","2026-10-12"],["Лауазым KZ","дәрігер"],["Бөлімше KZ","Терапия"],["Основание RU","Служебная записка"],["Негіз KZ","Қызметтік хат"]]) {
    fireEvent.change(screen.getByLabelText(label),{target:{value}});
  }
}

it("resolves version 13 after early recall selection and waits for that version's title before submitting",async()=>{
  let resolveVariants!: (value: Awaited<ReturnType<typeof getPersonnelOrderPublishedVariants>>) => void;
  let resolveTitle!: (value: Awaited<ReturnType<typeof getPersonnelOrderPublishedTemplateTitle>>) => void;
  vi.mocked(getPersonnelOrderPublishedVariants).mockImplementation(code=>code==='LEAVE.ANNUAL.RECALL'
    ? new Promise(resolve=>{resolveVariants=resolve;}) : Promise.resolve({items:[],independent_supported:false}));
  setup();
  vi.mocked(getPersonnelOrderPublishedTemplateTitle).mockImplementation(()=>new Promise(resolve=>{resolveTitle=resolve;}));
  await chooseTypeInMenu('LEAVE.ANNUAL.RECALL');await fillRecall();
  const submit=screen.getByRole('button',{name:'Создать приказ'});
  expect(submit).toBeDisabled();fireEvent.submit(submit.closest('form')!);
  expect(getPersonnelOrderPublishedTemplateTitle).not.toHaveBeenCalled();expect(createManualPersonnelOrderDraft).not.toHaveBeenCalled();
  await act(async()=>resolveVariants({items:[recallVariant],independent_supported:true}));
  await waitFor(()=>expect(getPersonnelOrderPublishedTemplateTitle).toHaveBeenLastCalledWith('LEAVE.ANNUAL.RECALL',13));
  expect(submit).toBeDisabled();fireEvent.submit(submit.closest('form')!);expect(previewPersonnelOrderHeaderDuplicate).not.toHaveBeenCalled();
  vi.mocked(previewPersonnelOrderHeaderDuplicate).mockResolvedValue({blocking:false,warnings:[],candidates:[]});
  vi.mocked(createManualPersonnelOrderDraft).mockResolvedValue({order_id:1} as never);
  await act(async()=>resolveTitle({...recallVariant,item_type_code:'LEAVE.ANNUAL.RECALL'}));
  await waitFor(()=>expect(submit).toBeEnabled());fireEvent.click(submit);
  await waitFor(()=>expect(createManualPersonnelOrderDraft).toHaveBeenCalledWith(expect.objectContaining({template_version_id:13,item_type_code:'LEAVE.ANNUAL.RECALL'})));
});

it("requires an explicit version when multiple variants arrive after early type selection",async()=>{
  let resolveVariants!: (value: Awaited<ReturnType<typeof getPersonnelOrderPublishedVariants>>) => void;
  vi.mocked(getPersonnelOrderPublishedVariants).mockImplementation(code=>code==='LEAVE.ANNUAL.RECALL'
    ? new Promise(resolve=>{resolveVariants=resolve;}) : Promise.resolve({items:[],independent_supported:false}));
  setup();await chooseTypeInMenu('LEAVE.ANNUAL.RECALL');await fillRecall();
  await act(async()=>resolveVariants({items:[recallVariant,{...recallVariant,template_id:9,template_version_id:14,name_kk:'Екінші үлгі'}],independent_supported:true}));
  expect(screen.getByRole('button',{name:'Создать приказ'})).toBeDisabled();expect(getPersonnelOrderPublishedTemplateTitle).not.toHaveBeenCalled();
  vi.mocked(getPersonnelOrderPublishedTemplateTitle).mockResolvedValue({...recallVariant,item_type_code:'LEAVE.ANNUAL.RECALL'});
  await chooseTypeInMenu('LEAVE.ANNUAL.RECALL');fireEvent.click(document.querySelector('[data-template-version="13"]')!);
  await fillRecall(false);
  await waitFor(()=>expect(screen.getByRole('button',{name:'Создать приказ'})).toBeEnabled());
  expect(getPersonnelOrderPublishedTemplateTitle).toHaveBeenLastCalledWith('LEAVE.ANNUAL.RECALL',13);
});

it("blocks independent creation if there is no published version",async()=>{
  vi.mocked(getPersonnelOrderPublishedVariants).mockResolvedValue({items:[],independent_supported:true});
  setup();await chooseTypeInMenu('LEAVE.ANNUAL.RECALL');await fillRecall();
  expect(screen.getByRole('button',{name:'Создать приказ'})).toBeDisabled();
  expect(getPersonnelOrderPublishedTemplateTitle).not.toHaveBeenCalled();fireEvent.submit(screen.getByRole('button',{name:'Создать приказ'}).closest('form')!);
  expect(createManualPersonnelOrderDraft).not.toHaveBeenCalled();
});

it("blocks a title response for the wrong version",async()=>{
  vi.mocked(getPersonnelOrderPublishedVariants).mockImplementation(async code=>({items:code==='LEAVE.ANNUAL.RECALL'?[recallVariant]:[],independent_supported:true}));
  setup();vi.mocked(getPersonnelOrderPublishedTemplateTitle).mockResolvedValue({...recallVariant,template_version_id:14,item_type_code:'LEAVE.ANNUAL.RECALL'});
  await chooseTypeInMenu('LEAVE.ANNUAL.RECALL');await fillRecall();
  expect(await screen.findByRole('alert')).toHaveTextContent('не соответствует выбранной версии');expect(screen.getByRole('button',{name:'Создать приказ'})).toBeDisabled();
  fireEvent.submit(screen.getByRole('button',{name:'Создать приказ'}).closest('form')!);expect(createManualPersonnelOrderDraft).not.toHaveBeenCalled();
});

async function selectType(type: "LEAVE.UNPAID.GRANT" | "LEAVE.CHILDCARE.GRANT" | "TRANSFER") {
  await chooseTypeInMenu(type);
  await waitFor(() => expect(getPersonnelOrderPublishedTemplateTitle).toHaveBeenLastCalledWith(type));
}

async function chooseTypeInMenu(type: string) {
  await waitFor(() => expect(screen.getByRole("button", { name: "Тип кадрового приказа" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "Тип кадрового приказа" }));
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: personnelOrderTypeLabel(type, "kk") } });
  fireEvent.click(screen.getByRole("menuitem", { name: personnelOrderTypeLabel(type, "kk") }));
}

it.each(['25','50'])('creates simple supplementary pay through server template 6/version 11 with %s percent and no replacement or rates', async percent=>{
  const variant={template_id:6,template_version_id:11,version_number:1,name_ru:'О дополнительной оплате',name_kk:'Қосымша ақы туралы',title_ru:'О дополнительной оплате',title_kk:'Қосымша ақы туралы',is_default:true};
  vi.mocked(getPersonnelOrderPublishedVariants).mockImplementation(async code=>({items:code==='SUPPLEMENTARY_PAY'?[variant]:[],independent_supported:true}));
  setup();
  vi.mocked(getPersonnelOrderPublishedTemplateTitle).mockResolvedValue({...variant,item_type_code:'SUPPLEMENTARY_PAY'});
  vi.mocked(getEmployee).mockResolvedValue({...employeeDetail,position:{id:24,name:'Машинист по стирке белья',name_kk:null},assignments:[]} as never);
  await chooseTypeInMenu('SUPPLEMENTARY_PAY');
  expect(screen.getByLabelText('Основание (RU)')).toHaveValue('Личное заявление');
  expect(screen.getByLabelText('Основание (KK)')).toHaveValue('Жеке өтініш');
  expect(screen.getByTestId('personnel-order-create-blockers')).not.toHaveTextContent('Заполните поле «Основание');
  const bases=percent==='25'?{ru:'Личное заявление',kk:'Жеке өтініш'}:{ru:'Служебная записка',kk:'Қызметтік хат'};
  if(percent==='50'){
    fireEvent.change(screen.getByLabelText('Основание (RU)'),{target:{value:bases.ru}});
    fireEvent.change(screen.getByLabelText('Основание (KK)'),{target:{value:bases.kk}});
  }
  await selectEmployee();
  expect(screen.getByLabelText('Должность получателя (KK)')).toHaveValue('');
  await waitFor(()=>expect(screen.getByLabelText('Должность получателя в дательном падеже (RU)')).toHaveValue('машинисту по стирке белья'));
  expect(screen.queryByTestId('personnel-order-text-forms')).not.toBeInTheDocument();
  expect(screen.queryByText(/Заполните КК-должность вручную/)).not.toBeInTheDocument();
  expect(screen.getByLabelText('Основание (RU)')).toHaveValue(bases.ru);
  expect(screen.getByLabelText('Основание (KK)')).toHaveValue(bases.kk);
  const selector=await screen.findByRole('combobox',{name:'Доплата'});
  expect(Array.from(selector.querySelectorAll('option')).map(o=>o.value)).toEqual(['','25','50']);
  expect(screen.queryByTestId('replacement-fields')).not.toBeInTheDocument();
  for(const label of ['Дополнительная ставка','Общая ставка','Замещаемый сотрудник (RU)','База расчёта доплаты (RU)'])expect(screen.queryByLabelText(label)).not.toBeInTheDocument();
  for(const [label,value] of [['Номер приказа','TEST-simple-pay'],['Дата приказа','2026-10-10'],['Дата действия','2026-02-02']])fireEvent.change(screen.getByLabelText(label),{target:{value}});
  const submit=screen.getByRole('button',{name:'Создать приказ'});
  expect(submit).toBeDisabled();
  fireEvent.change(selector,{target:{value:percent}});
  vi.mocked(previewPersonnelOrderHeaderDuplicate).mockResolvedValue({blocking:false,warnings:[],candidates:[]});
  vi.mocked(createManualPersonnelOrderDraft).mockResolvedValue({order_id:1} as never);
  await waitFor(()=>expect(screen.queryByTestId('personnel-order-create-blockers')?.textContent||'').toBe(''));
  expect(submit).toBeEnabled();
  expect(screen.getByLabelText('ФИО в дательном падеже (RU)')).not.toHaveValue('');
  fireEvent.click(submit);
  await waitFor(()=>expect(createManualPersonnelOrderDraft).toHaveBeenCalledWith(expect.objectContaining({template_version_id:11,item_type_code:'SUPPLEMENTARY_PAY',effective_date:'2026-02-02',item_payload:expect.objectContaining({allowance:expect.objectContaining({percent:Number(percent),basis_type:'RECIPIENT_BASE_SALARY',basis_ru:bases.ru,basis_kk:bases.kk})})})));
  const payload=vi.mocked(createManualPersonnelOrderDraft).mock.calls[0][0].item_payload!;
  expect(payload.allowance_recipient).toEqual(expect.objectContaining({position_kk:''}));
  expect(payload).not.toHaveProperty('replacement');expect(payload).not.toHaveProperty('concurrent');
});

async function selectUnpaid() {
  await selectType("LEAVE.UNPAID.GRANT");
  await waitFor(() => expect(screen.getByLabelText("Название приказа")).toHaveValue(unpaidTitles.title_kk));
}

async function selectEmployee() {
  fireEvent.change(screen.getByLabelText("Сотрудник"), { target: { value: "Иль" } });
  fireEvent.click(await screen.findByRole("option", { name: /^Ильясова Ассель Адиловна/ }));
  await waitFor(() => expect(screen.getByTestId("selected-employee-id")).toHaveValue("383"));
}

async function fillValidUnpaid() {
  await selectUnpaid();
  await selectEmployee();
  fireEvent.change(screen.getByLabelText("Номер приказа"), { target: { value: "T-1" } });
  fireEvent.change(screen.getByLabelText("Дата приказа"), { target: { value: "2026-07-01" } });
  fireEvent.change(screen.getByLabelText("Дата начала"), { target: { value: "2026-07-17" } });
}

it.each(PERSONNEL_ORDER_CREATE_TYPE_OPTIONS.map(option => option.value))("offers canonical and editable job forms for create %s", async type => {
  setup();
  vi.mocked(getEmployee).mockResolvedValue({ ...employeeDetail, assignments: [], has_current_assignment: true, position: { ...employee.position, job_code: "PHYSICIAN", job_nameru: "Врач каталога", job_namekk: "Дәрігер", job_namekk_doc: "дәрігері каталога" } });
  await chooseTypeInMenu(type);
  await selectEmployee();
  if(type === "LEAVE.ANNUAL.RECALL") {
    expect(screen.getByLabelText("Должность")).toHaveValue("Врач каталога");
    expect(screen.getByLabelText("Лауазым KZ")).toHaveValue("Дәрігер");
    fireEvent.change(screen.getByLabelText("Лауазым KZ"),{target:{value:"Ручная форма"}});
    expect(screen.getByLabelText("Лауазым KZ")).toHaveValue("Ручная форма");return;
  }
  if (type === "CONCURRENT_DUTY_END") {
    expect(screen.getByLabelText("Дополнительная должность (RU)")).toHaveValue("");
    expect(screen.getByLabelText("ФИО в родительном падеже (RU)")).toHaveValue("");
    expect(screen.getByLabelText("Оставшаяся общая ставка")).toHaveValue(null);
    return;
  }
  if (type === "CONCURRENT_DUTY_START") {
    expect(screen.getByLabelText("Дополнительная должность (RU)")).toHaveValue("");
    expect(screen.getByLabelText("ФИО в дательном падеже (RU)")).toHaveValue("");
    return;
  }
  if (type === "TRANSFER") {
    expect(screen.getByLabelText("Новая должность (RU)")).toHaveValue("");
    fireEvent.change(screen.getByLabelText("Новая должность (KK)"), { target: { value: "Дәрігер" } });
    expect(screen.getByLabelText("Новая должность (KK)")).toHaveValue("Дәрігер");
    return;
  }
  if (type === "SUPPLEMENTARY_PAY") {
    await waitFor(()=>expect(screen.getByLabelText('Должность получателя (RU)')).toHaveValue('Врач каталога'));
    expect(screen.getByLabelText('Должность получателя (KK)')).toHaveValue('дәрігері каталога');
    fireEvent.change(screen.getByLabelText('Должность получателя (KK)'), {target: {value: 'Ручная форма'}});
    expect(screen.getByLabelText('Должность получателя (KK)')).toHaveValue('Ручная форма');
    expect(screen.queryByTestId('personnel-order-text-forms')).not.toBeInTheDocument();
    return;
  }
  expect(screen.getByLabelText("Должность в тексте приказа (RU)")).toHaveValue("Врач каталога");
  expect(screen.getByLabelText("Должность в тексте приказа (KK)")).toHaveValue("дәрігері каталога");
  fireEvent.change(screen.getByLabelText("Должность в тексте приказа (KK)"), { target: { value: "Ручная форма" } });
  expect(screen.getByLabelText("Должность в тексте приказа (KK)")).toHaveValue("Ручная форма");
});

it.each(["LEAVE.CHILDCARE.GRANT", "LEAVE.UNPAID.GRANT"] as const)("autofills actual API Медсестра in create %s", async (type) => {
  setup();
  vi.mocked(getEmployee).mockResolvedValue({ ...employeeDetail, position: { id: 27, name: "Медсестра", name_kk: "мейіргер" } });
  await selectType(type);
  await selectEmployee();
  await waitFor(() => expect(screen.getByLabelText("Должность в тексте приказа (KK)")).toHaveValue("мейіргері"));
  expect(screen.getByLabelText("Должность в тексте приказа (RU)")).toHaveValue("медсестра");
  expect(screen.queryByText(/Необходимо заполнить:/)).not.toBeInTheDocument();
});

it.each(["LEAVE.CHILDCARE.GRANT", "LEAVE.UNPAID.GRANT"] as const)("uses arbitrary catalogue positions and warns only for missing KK in %s", async type => {
  setup();
  vi.mocked(getEmployee).mockResolvedValue({ ...employeeDetail, position: { id: 44, name: "сестра-хозяйка", name_kk: "шаруа бикесі" } });
  await selectType(type); await selectEmployee();
  expect(screen.getByLabelText("Должность в тексте приказа (KK)")).toHaveValue("шаруа бикесі");
  expect(screen.getByLabelText("Должность в тексте приказа (RU)")).toHaveValue("сестра-хозяйка");
  fireEvent.change(screen.getByLabelText("Должность в тексте приказа (KK)"), { target: { value: "Ручная форма первого сотрудника" } });
  fireEvent.click(screen.getByRole("button", { name: "Сменить сотрудника" }));
  const second = { ...employeeDetail, id: "777", fio: "Ильясова Анна Сергеевна", position: { id: 3, name: "Бухгалтер", name_kk: null } };
  vi.mocked(getEmployees).mockResolvedValue({ items: [employee, second], total: 2 });
  vi.mocked(getEmployee).mockResolvedValue(second);
  fireEvent.change(screen.getByLabelText("Сотрудник"), { target: { value: "Ильясова" } });
  fireEvent.click(await screen.findByRole("option", { name: second.fio }));
  await waitFor(() => expect(getEmployee).toHaveBeenLastCalledWith("777"));
  await waitFor(() => expect(screen.getByLabelText("Должность в тексте приказа (RU)")).toHaveValue("бухгалтер"));
  expect(screen.getByLabelText("Должность в тексте приказа (RU)")).toHaveValue("бухгалтер");
  expect(screen.getByLabelText("Должность в тексте приказа (KK)")).toHaveValue("");
  expect(screen.getByText(/В справочнике должности нет казахского названия/)).toBeInTheDocument();
});

it.each(["LEAVE.CHILDCARE.GRANT", "LEAVE.UNPAID.GRANT"] as const)("preserves manual position edits across late detail, then refreshes on employee change in %s", async (type) => {
  const { rerender, onClose, onCreated } = setup();
  await selectType(type);
  await selectEmployee();
  const nurse = { ...employeeDetail, id: "618", fio: "Адилова Жадыра Хабибуловна", position: { id: 27, name: "Медсестра", name_kk: "мейіргер" },
    document_forms_ru: { position_document_nominative_ru: "Сохранённая RU" },
    document_forms_kk: { position_document_possessive_kk: "Сохранённая KK" },
  };
  vi.mocked(getEmployees).mockResolvedValue({ items: [nurse], total: 1 });
  let resolveDetail!: (value: typeof nurse) => void;
  vi.mocked(getEmployee).mockResolvedValueOnce(nurse).mockReturnValueOnce(new Promise(resolve => { resolveDetail = resolve; }));
  rerender(<PersonnelOrderCreateDialog open onClose={onClose} onCreated={onCreated} initialEmployeeId={618} />);
  const ru = screen.getByLabelText("Должность в тексте приказа (RU)");
  const kk = screen.getByLabelText("Должность в тексте приказа (KK)");
  await waitFor(() => expect(ru).toHaveValue("")); expect(kk).toHaveValue("");
  fireEvent.change(ru, { target: { value: "Ручная RU" } });
  fireEvent.change(kk, { target: { value: "Ручная KK" } });
  const unit = screen.getByLabelText("Подразделение в тексте приказа (KK)");
  fireEvent.change(unit, { target: { value: "Ручное подразделение" } });
  resolveDetail(nurse);
  await waitFor(() => expect(screen.getByLabelText("Должность")).toHaveValue("Медсестра"));
  expect(ru).toHaveValue("Ручная RU"); expect(kk).toHaveValue("Ручная KK");
  expect(unit).toHaveValue("Ручное подразделение");
  fireEvent.change(screen.getByLabelText("Дата начала"), { target: { value: "2026-08-01" } });
  expect(ru).toHaveValue("Ручная RU"); expect(kk).toHaveValue("Ручная KK");
  vi.mocked(getEmployee).mockResolvedValue({ ...nurse, id: "619" });
  rerender(<PersonnelOrderCreateDialog open onClose={onClose} onCreated={onCreated} initialEmployeeId={619} />);
  await waitFor(() => expect(ru).toHaveValue("Сохранённая RU"));
  expect(kk).toHaveValue("Сохранённая KK");
  expect(createManualPersonnelOrderDraft).not.toHaveBeenCalled();
});

it("starts without a type, template request, title, employee fields, or enabled Create", () => {
  setup();
  expect(screen.getByLabelText("Тип кадрового приказа")).toHaveValue("");
  expect(screen.getByLabelText("Название приказа")).toHaveValue("");
  expect(screen.queryByLabelText("Сотрудник")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Создать приказ" })).toBeDisabled();
  expect(getPersonnelOrderPublishedTemplateTitle).not.toHaveBeenCalled();
  expect(getEmployees).not.toHaveBeenCalled();
  expect(getEmployee).not.toHaveBeenCalled();
});

it("creates childcare leave with separate application/certificate and saved document forms", async () => {
  setup();
  vi.mocked(previewPersonnelOrderHeaderDuplicate).mockResolvedValue({ blocking: false } as any);
  vi.mocked(createManualPersonnelOrderDraft).mockResolvedValue({ order_id: 123 } as any);
  await selectType("LEAVE.CHILDCARE.GRANT");
  await selectEmployee();
  expect(screen.getByLabelText("ФИО сотрудника в родительном падеже (RU)")).toHaveValue("Ильясовой Ассель Адиловны");
  for (const [label, value] of Object.entries({
    "Номер приказа": "CHILD-TEST", "Дата приказа": "2026-07-28", "Дата начала": "2026-08-01", "Дата окончания": "2029-02-13",
    "Дата заявления": "2026-07-28", "Номер заявления": "APP-17", "Дата выдачи свидетельства о рождении": "2026-02-13", "Номер свидетельства о рождении": "9967264",
    "ФИО сотрудника в дательном падеже (RU)": "Ильясовой Ассель Адиловне",
  })) fireEvent.change(screen.getByLabelText(label), { target: { value } });
  expect(screen.getByLabelText("Дата окончания")).toHaveValue("2029-02-13");
  fireEvent.click(screen.getByRole("button", { name: "Создать приказ" }));
  await waitFor(() => expect(createManualPersonnelOrderDraft).toHaveBeenCalled());
  expect(vi.mocked(createManualPersonnelOrderDraft).mock.calls[0][0]).toMatchObject({ item_payload: {
    leave_start: "2026-08-01", leave_end: "2029-02-13",
    basis: { kind: "PERSONAL_APPLICATION", date: "2026-07-28", number: "APP-17", birth_certificate: { date: "2026-02-13", number: "9967264" } },
    document_forms_kk: { org_unit_document_genitive_kk: "Сәулелік диагностика бөлімшесінің" },
    document_forms_ru: { employee_full_name_genitive_ru: "Ильясовой Ассель Адиловны" },
  } });
});

it("prefers a saved RU genitive and preserves manual text across rerenders", async () => {
  setup();
  vi.mocked(getEmployee).mockResolvedValue({ ...employeeDetail, document_forms_ru: { employee_full_name_genitive_ru: "Сохранённая документная форма" } } as typeof employeeDetail);
  await selectType("LEAVE.CHILDCARE.GRANT");
  await selectEmployee();
  const field = screen.getByLabelText("ФИО сотрудника в родительном падеже (RU)");
  expect(field).toHaveValue("Сохранённая документная форма");
  fireEvent.change(field, { target: { value: "Ручная корректировка" } });
  fireEvent.change(screen.getByLabelText("Дата заявления"), { target: { value: "2026-07-29" } });
  fireEvent.change(screen.getByLabelText("Язык"), { target: { value: "ru" } });
  await waitFor(() => expect(screen.getByLabelText("Название приказа")).toHaveValue(unpaidTitles.title_ru));
  expect(field).toHaveValue("Ручная корректировка");
});

it("does not overwrite RU genitive typed while employee detail is pending", async () => {
  setup();
  let resolveDetail!: (value: typeof employeeDetail) => void;
  vi.mocked(getEmployee).mockReturnValue(new Promise(resolve => { resolveDetail = resolve; }));
  await selectType("LEAVE.CHILDCARE.GRANT");
  fireEvent.change(screen.getByLabelText("Сотрудник"), { target: { value: "Иль" } });
  fireEvent.click(await screen.findByRole("option", { name: employee.fio }));
  fireEvent.change(screen.getByLabelText("ФИО сотрудника в родительном падеже (RU)"), { target: { value: "Введено до ответа" } });
  resolveDetail(employeeDetail);
  await waitFor(() => expect(screen.getByLabelText("Подразделение")).toBeInTheDocument());
  expect(screen.getByLabelText("ФИО сотрудника в родительном падеже (RU)")).toHaveValue("Введено до ответа");
});

it("renders a dialog with dedicated header, scrollable body, and sticky footer", async () => {
  setup();
  await selectUnpaid();
  expect(screen.getByRole("dialog", { name: "Создать приказ" })).toBeInTheDocument();
  expect(screen.getByTestId("personnel-order-create-header")).toHaveTextContent("Будет создан новый приказ в статусе DRAFT");
  expect(screen.getByTestId("personnel-order-create-body")).toHaveClass("overflow-y-auto");
  expect(screen.getByTestId("personnel-order-create-footer")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Отмена" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Создать приказ" })).toBeInTheDocument();
});

it("selecting unpaid shows only its current-language PUBLISHED title and unpaid fields", async () => {
  setup();
  await selectUnpaid();
  expect(screen.getByLabelText("Дата начала")).toBeInTheDocument();
  expect(screen.getByLabelText("Название приказа")).toHaveAttribute("readonly");
  expect(screen.queryByLabelText("Дата действия")).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Язык"), { target: { value: "ru" } });
  await waitFor(() => expect(screen.getByLabelText("Название приказа")).toHaveValue(unpaidTitles.title_ru));
  expect(getPersonnelOrderPublishedTemplateTitle).toHaveBeenLastCalledWith("LEAVE.UNPAID.GRANT");
});

it("never displays the unpaid title after TRANSFER is selected", async () => {
  setup();
  await selectUnpaid();
  await selectType("TRANSFER");
  await waitFor(() => expect(screen.getByLabelText("Название приказа")).toHaveValue(transferTitles.title_kk));
  expect(screen.getByLabelText("Название приказа")).not.toHaveValue(unpaidTitles.title_kk);
  expect(screen.getByLabelText("Дата действия")).toBeInTheDocument();
  expect(screen.queryByLabelText("Дата начала")).not.toBeInTheDocument();
});

it("ignores an old unpaid response when type changes to TRANSFER before it resolves", async () => {
  let resolveUnpaid: ((value: typeof unpaidTitles) => void) | undefined;
  let resolveTransfer: ((value: typeof transferTitles) => void) | undefined;
  vi.mocked(getPersonnelOrderPublishedTemplateTitle).mockImplementation((type) => new Promise((resolve) => {
    if (type === "LEAVE.UNPAID.GRANT") resolveUnpaid = resolve as (value: typeof unpaidTitles) => void;
    else resolveTransfer = resolve as (value: typeof transferTitles) => void;
  }));
  render(<PersonnelOrderCreateDialog open onClose={vi.fn()} onCreated={vi.fn()} />);
  await selectType("LEAVE.UNPAID.GRANT");
  await selectType("TRANSFER");
  resolveTransfer?.(transferTitles);
  await waitFor(() => expect(screen.getByLabelText("Название приказа")).toHaveValue(transferTitles.title_kk));
  resolveUnpaid?.(unpaidTitles);
  await waitFor(() => expect(screen.getByLabelText("Название приказа")).not.toHaveValue(unpaidTitles.title_kk));
});

it("clears previous leave dates and document forms when type changes", async () => {
  setup();
  await selectUnpaid();
  await selectEmployee();
  fireEvent.change(screen.getByLabelText("Дата начала"), { target: { value: "2026-07-17" } });
  fireEvent.change(screen.getByLabelText("ФИО сотрудника в дательном падеже (KK)"), { target: { value: "Тестоваға" } });
  await selectType("TRANSFER");
  await selectType("LEAVE.UNPAID.GRANT");
  expect(screen.getByLabelText("Дата начала")).toHaveValue("");
  expect(screen.getByLabelText("Дата окончания")).toHaveValue("");
  expect(screen.getByLabelText("ФИО сотрудника в дательном падеже (KK)")).toHaveValue("");
});

it("uses a canonical title when PUBLISHED template is absent", async () => {
  setup();
  vi.mocked(getPersonnelOrderPublishedTemplateTitle).mockRejectedValueOnce(new Error("not found"));
  await selectType("TRANSFER");
  expect(await screen.findByRole("alert")).toHaveTextContent("not found");
  expect(screen.getByRole("button",{name:"Создать приказ"})).toBeDisabled();
  expect(screen.getByLabelText("Название приказа")).toHaveValue("Ауыстыру туралы");
  expect(createManualPersonnelOrderDraft).not.toHaveBeenCalled();
});

it("prefills the approved childcare titles in both languages without a published version", async () => {
  setup();
  vi.mocked(getPersonnelOrderPublishedTemplateTitle).mockRejectedValue(new Error("not found"));
  await selectType("LEAVE.CHILDCARE.GRANT");
  expect(await screen.findByRole("alert")).toHaveTextContent("not found");
  expect(screen.getByLabelText("Название приказа")).toHaveValue("Бала күтіміне байланысты жалақы сақталмайтын демалыс туралы");
  fireEvent.change(screen.getByLabelText("Язык"), { target: { value: "ru" } });
  await waitFor(() => expect(screen.getByLabelText("Название приказа")).toHaveValue("О неоплачиваемом отпуске по уходу за ребенком"));
  expect(createManualPersonnelOrderDraft).not.toHaveBeenCalled();
});

it("loads only a read-only template GET while the dialog is opened and a type is selected", async () => {
  setup();
  await selectUnpaid();
  expect(getPersonnelOrderPublishedTemplateTitle).toHaveBeenCalledTimes(1);
  expect(previewPersonnelOrderHeaderDuplicate).not.toHaveBeenCalled();
  expect(createManualPersonnelOrderDraft).not.toHaveBeenCalled();
});

it("loads the primary assignment and keeps the footer after the unpaid KK fields appear", async () => {
  setup();
  await selectUnpaid();
  await selectEmployee();
  expect(screen.getByLabelText("Подразделение")).toHaveValue("59");
  expect(screen.getByLabelText("Должность")).toHaveValue("Врач");
  fireEvent.change(screen.getByLabelText("Дата начала"), { target: { value: "2026-07-07" } });
  expect(screen.getByLabelText("Дата окончания")).toHaveValue("2026-07-07");
  expect(screen.getByLabelText("ФИО сотрудника в родительном падеже (KK)")).toBeInTheDocument();
  expect(screen.getByTestId("personnel-order-create-footer")).toContainElement(screen.getByRole("button", { name: "Создать приказ" }));
});

it("closes without saving through Cancel and keeps Create disabled while required data is missing", async () => {
  const { onClose } = setup();
  await selectUnpaid();
  expect(screen.getByRole("button", { name: "Создать приказ" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Отмена" }));
  expect(onClose).toHaveBeenCalledTimes(1);
  expect(createManualPersonnelOrderDraft).not.toHaveBeenCalled();
});

it("blocks an invalid reverse unpaid range before request submission", async () => {
  setup();
  await fillValidUnpaid();
  fireEvent.change(screen.getByLabelText("Дата окончания"), { target: { value: "2026-07-10" } });
  expect(screen.getByRole("button", { name: "Создать приказ" })).toBeDisabled();
  expect(createManualPersonnelOrderDraft).not.toHaveBeenCalled();
});

it("keeps Create disabled and names missing document forms", async () => {
  setup();
  vi.mocked(getEmployee).mockResolvedValueOnce({ ...employee, org_unit: { ...employee.org_unit, unit_id: 999 }, position: { ...employee.position, id: 999 } });
  await selectUnpaid();
  await selectEmployee();
  fireEvent.change(screen.getByLabelText("Номер приказа"), { target: { value: "T-1" } });
  fireEvent.change(screen.getByLabelText("Дата приказа"), { target: { value: "2026-07-01" } });
  fireEvent.change(screen.getByLabelText("Дата начала"), { target: { value: "2026-07-17" } });
  expect(screen.getByRole("button", { name: "Создать приказ" })).toBeDisabled();
  expect(screen.getByRole("alert")).toHaveTextContent("Подразделение в тексте приказа (KK)");
  expect(createManualPersonnelOrderDraft).not.toHaveBeenCalled();
});

it("fills Ilyasova's actual active-assignment document forms from the API detail and keeps them collapsed", async () => {
  setup();
  await fillValidUnpaid();

  const forms = screen.getByTestId("personnel-order-text-forms");
  expect(forms).not.toHaveAttribute("open");
  expect(forms).toHaveTextContent("Формы для текста приказа заполнены автоматически");
  expect(screen.queryByText("В справочнике отсутствует казахское название выбранного подразделения.")).not.toBeInTheDocument();
  expect(screen.getByLabelText("Подразделение в тексте приказа (KK)")).toHaveValue("Сәулелік диагностика бөлімшесінің");
  expect(screen.getByLabelText("Должность в тексте приказа (KK)")).toHaveValue("дәрігері");
  expect(screen.getByLabelText("Должность в тексте приказа (RU)")).toHaveValue("врач");
  expect(screen.getByLabelText("ФИО сотрудника в дательном падеже (KK)")).toHaveValue("Ассель Адиловна Ильясоваға");
  expect(screen.getByLabelText("ФИО сотрудника в родительном падеже (KK)")).toHaveValue("Ассель Адиловна Ильясованың");
  expect(screen.getByLabelText("ФИО сотрудника в дательном падеже (RU)")).toHaveValue("Ильясовой Ассель Адиловне");
  expect(screen.getByRole("button", { name: "Создать приказ" })).toBeEnabled();

  vi.mocked(previewPersonnelOrderHeaderDuplicate).mockResolvedValue({ blocking: false, warnings: [], candidates: [] });
  vi.mocked(createManualPersonnelOrderDraft).mockResolvedValue({ order_id: 1 } as never);
  fireEvent.click(screen.getByRole("button", { name: "Создать приказ" }));
  await waitFor(() => expect(createManualPersonnelOrderDraft).toHaveBeenCalledWith(expect.objectContaining({
    item_payload: expect.objectContaining({
      document_forms_kk: expect.objectContaining({ position_document_possessive_kk: "дәрігері" }),
      document_forms_ru: expect.objectContaining({ position_document_nominative_ru: "врач", employee_full_name_dative_ru: "Ильясовой Ассель Адиловне" }),
    }),
  })));
});

it("keeps actual API document forms after asynchronous detail loading and a subsequent rerender", async () => {
  setup();
  let resolveDetail: ((value: typeof employeeDetail) => void) | undefined;
  vi.mocked(getEmployee).mockImplementationOnce(() => new Promise((resolve) => { resolveDetail = resolve as (value: typeof employeeDetail) => void; }));
  await selectUnpaid();
  fireEvent.change(screen.getByLabelText("Сотрудник"), { target: { value: "Иль" } });
  fireEvent.click(await screen.findByRole("option", { name: "Ильясова Ассель Адиловна" }));
  expect(screen.queryByTestId("personnel-order-text-forms")).not.toBeInTheDocument();

  resolveDetail?.(employeeDetail);
  const forms = await screen.findByTestId("personnel-order-text-forms");
  fireEvent.change(screen.getByLabelText("Язык"), { target: { value: "ru" } });

  expect(forms).not.toHaveAttribute("open");
  expect(screen.getByLabelText("Должность в тексте приказа (KK)")).toHaveValue("дәрігері");
  expect(screen.getByLabelText("Должность в тексте приказа (RU)")).toHaveValue("врач");
  expect(screen.getByLabelText("ФИО сотрудника в дательном падеже (RU)")).toHaveValue("Ильясовой Ассель Адиловне");
});

it("uses the directory Kazakh name when its order-text form is absent and preserves a manual edit on rerender", async () => {
  setup();
  vi.mocked(getEmployee).mockResolvedValueOnce({
    ...employeeDetail,
    org_unit: { ...employee.org_unit, name_kk: "Сәулелік диагностика бөлімшесі", document_genitive_kk: null },
  });
  await selectUnpaid();
  await selectEmployee();
  const field = screen.getByLabelText("Подразделение в тексте приказа (KK)");
    expect(field).toHaveValue("Сәулелік диагностика бөлімшесінің");
  fireEvent.change(field, { target: { value: "Ручная форма" } });
  fireEvent.change(screen.getByLabelText("Язык"), { target: { value: "ru" } });
  expect(field).toHaveValue("Ручная форма");
});

it("replaces the order-text department form from the selected directory unit", async () => {
  setup();
  await selectUnpaid();
  await selectEmployee();
  const department = screen.getByLabelText("Подразделение");
  await waitFor(() => expect(screen.getByRole("option", { name: "Лучевая диагностика" })).toBeInTheDocument());
  fireEvent.change(department, { target: { value: "41" } });
  expect(screen.getByLabelText("Подразделение в тексте приказа (KK)")).toHaveValue("");
  expect(screen.getByText("В справочнике отсутствует казахское название выбранного подразделения.")).toBeInTheDocument();
  fireEvent.change(department, { target: { value: "59" } });
  expect(screen.getByLabelText("Подразделение в тексте приказа (KK)")).toHaveValue("Сәулелік диагностика бөлімшесінің");
  expect(screen.queryByText("В справочнике отсутствует казахское название выбранного подразделения.")).not.toBeInTheDocument();
});

it("keeps automatic employee-selected department text while the directory finishes loading", async () => {
  let resolveCatalog: ((items: Array<{ unit_id: number; name: string; group_id: number | null; name_kk?: string | null; document_genitive_kk?: string | null }>) => void) | undefined;
  vi.mocked(loadOrgUnitSelectOptions).mockImplementationOnce(() => new Promise((resolve) => { resolveCatalog = resolve; }));
  setup();
  await selectUnpaid();
  await selectEmployee();
  const field = screen.getByLabelText("Подразделение в тексте приказа (KK)");
  expect(field).toHaveValue("Сәулелік диагностика бөлімшесінің");
  resolveCatalog?.([{ unit_id: 59, name: "Лучевая диагностика", group_id: 2, name_kk: "Сәулелік диагностика бөлімшесі", document_genitive_kk: "Сәулелік диагностика бөлімшесінің" }]);
  await waitFor(() => expect(field).toHaveValue("Сәулелік диагностика бөлімшесінің"));
  fireEvent.change(field, { target: { value: "Ручная форма" } });
  fireEvent.change(screen.getByLabelText("Язык"), { target: { value: "ru" } });
  expect(field).toHaveValue("Ручная форма");
});

it("keeps a manual department-text edit when the dialog is closed and reopened", async () => {
  vi.mocked(getPersonnelOrderPublishedTemplateTitle).mockResolvedValue(unpaidTitles);
  vi.mocked(getEmployees).mockResolvedValue({ items: [employee], total: 1 });
  vi.mocked(getEmployee).mockResolvedValue(employeeDetail);
  vi.mocked(loadOrgUnitSelectOptions).mockResolvedValue([{ unit_id: 59, name: "Лучевая диагностика", group_id: 2, document_genitive_kk: "Сәулелік диагностика бөлімшесінің" }]);
  const view = render(<PersonnelOrderCreateDialog open onClose={vi.fn()} onCreated={vi.fn()} />);
  await selectUnpaid();
  await selectEmployee();
  const field = screen.getByLabelText("Подразделение в тексте приказа (KK)");
  fireEvent.change(field, { target: { value: "Ручная форма" } });
  view.rerender(<PersonnelOrderCreateDialog open={false} onClose={vi.fn()} onCreated={vi.fn()} />);
  view.rerender(<PersonnelOrderCreateDialog open onClose={vi.fn()} onCreated={vi.fn()} />);
  expect(screen.getByLabelText("Подразделение в тексте приказа (KK)")).toHaveValue("Ручная форма");
});

it("identifies a missing Kazakh directory name next to the editable field", async () => {
  setup();
  vi.mocked(getEmployee).mockResolvedValueOnce({ ...employeeDetail, org_unit: { ...employee.org_unit, unit_id: 999 } });
  await selectUnpaid();
  await selectEmployee();
  expect(screen.getByText("В справочнике отсутствует казахское название выбранного подразделения.")).toBeInTheDocument();
  expect(screen.getByLabelText("Подразделение в тексте приказа (KK)")).toBeEnabled();
});

it("prevents a second request while the first create request is pending", async () => {
  setup();
  await fillValidUnpaid();
  vi.mocked(previewPersonnelOrderHeaderDuplicate).mockResolvedValue({ blocking: false, warnings: [], candidates: [] });
  let resolveCreate: ((value: never) => void) | undefined;
  vi.mocked(createManualPersonnelOrderDraft).mockImplementationOnce(() => new Promise((resolve) => { resolveCreate = resolve as (value: never) => void; }));
  const create = screen.getByRole("button", { name: "Создать приказ" });
  fireEvent.click(create);
  fireEvent.click(create);
  await waitFor(() => expect(createManualPersonnelOrderDraft).toHaveBeenCalledTimes(1));
  expect(screen.getByRole("button", { name: "Создание…" })).toBeDisabled();
  resolveCreate?.({ order_id: 1 } as never);
});

it("shows all required-field blockers beside Create and removes them when complete", async () => {
  setup();
  const blockers=screen.getByTestId("personnel-order-create-blockers");
  expect(screen.getByTestId("personnel-order-create-footer")).toContainElement(blockers);
  expect(blockers).toHaveTextContent("Бұйрық нөмірін енгізіңіз");
  expect(blockers).toHaveTextContent("Қызметкерді үміткерлер тізімінен таңдаңыз");
  expect(screen.getByRole("button",{name:"Создать приказ"})).toHaveAttribute("aria-describedby","personnel-order-create-blockers");
  await fillValidUnpaid();
  expect(screen.queryByTestId("personnel-order-create-blockers")).not.toBeInTheDocument();
});

it("keeps the schema blocker beside Create even after required recall fields are filled", async () => {
  vi.mocked(getPersonnelOrderPublishedVariants).mockResolvedValue({items:[],creation_supported:false,creation_reason:"Схема не поддерживает отзыв"});
  setup();
  vi.mocked(getEmployee).mockResolvedValueOnce({...employeeDetail,position:{...employee.position,name_kk:null}});
  await chooseTypeInMenu("LEAVE.ANNUAL.RECALL");await selectEmployee();
  await waitFor(()=>expect(screen.getByTestId("personnel-order-create-blockers")).toHaveTextContent("Қазіргі ДБ құрылымы"));
  expect(screen.getByTestId("recall-position-kz-missing")).toBeInTheDocument();
  const field=screen.getByLabelText("Лауазым KZ");
  expect(field).toBeEnabled();fireEvent.change(field,{target:{value:"дәрігер"}});
  expect(field).toHaveValue("дәрігер");
  expect(screen.getByTestId("personnel-order-create-blockers")).not.toHaveTextContent("Лауазымды KZ тілінде толтырыңыз");
  expect(screen.getByRole("button",{name:"Создать приказ"})).toBeDisabled();
});


it("requires transfer destination, rate and bilingual basis, then opens the created order", async () => {
  const {onCreated, onClose} = setup();
  await selectType("TRANSFER"); await selectEmployee();
  fireEvent.change(screen.getByLabelText("Номер приказа"), {target:{value:"TRANSFER-TEST"}});
  fireEvent.change(screen.getByLabelText("Дата приказа"), {target:{value:"2026-10-08"}});
  fireEvent.change(screen.getByLabelText("Дата действия"), {target:{value:"2026-10-09"}});
  expect(screen.getByRole("button",{name:"Создать приказ"})).toBeDisabled();
  expect(screen.getByTestId("personnel-order-create-blockers")).toHaveTextContent("Основание перевода (KK)");
  for (const [label,value] of [["Новая должность (RU)","Врач"],["Новая должность (KK)","Дәрігер"],["Новое подразделение (RU)","Терапия"],["Новое подразделение (KK)","Терапия бөлімшесі"],["Ставка после перевода","0.5"],["Основание перевода (RU)","Заявление"],["Основание перевода (KK)","Өтініш"]]) fireEvent.change(screen.getByLabelText(label),{target:{value}});
  vi.mocked(previewPersonnelOrderHeaderDuplicate).mockResolvedValue({blocking:false,warnings:[],candidates:[]});
  const result = {order_id:77} as never; vi.mocked(createManualPersonnelOrderDraft).mockResolvedValue(result);
  await waitFor(() => expect(screen.getByRole("button",{name:"Создать приказ"})).toBeEnabled());
  fireEvent.click(screen.getByRole("button",{name:"Создать приказ"}));
  await waitFor(() => expect(onCreated).toHaveBeenCalledWith(result)); expect(onClose).toHaveBeenCalled();
  expect(createManualPersonnelOrderDraft).toHaveBeenCalledWith(expect.objectContaining({employee_id:383,item_payload:{transfer:{position_ru:"Врач",position_kk:"Дәрігер",org_unit_ru:"Терапия",org_unit_kk:"Терапия бөлімшесі",rate:0.5,basis_ru:"Заявление",basis_kk:"Өтініш"}}}));
});

it("submits only explicit additional placement, dative names and concurrent rates", async () => {
  const {onCreated} = setup();await chooseTypeInMenu("CONCURRENT_DUTY_START");await selectEmployee();
  for(const [label,value] of [["Номер приказа","CONCURRENT-TEST"],["Дата приказа","2026-05-21"],["Дата действия","2026-05-21"],["Дополнительная должность (RU)","Врач"],["Дополнительная должность (KK)","дәрігер"],["Дополнительное подразделение (RU)","Терапия"],["Дополнительное подразделение (KK)","терапия бөлімшесінің"],["Дополнительная должность в родительном падеже (RU)","врача"],["Дополнительное подразделение в родительном падеже (RU)","отделения терапии"],["ФИО в дательном падеже (RU)","Ильясовой Ассель Адиловне"],["ФИО в дательном падеже (KK)","Ассель Адиловна Ильясоваға"],["Дополнительная ставка","0.5"],["Общая ставка","1.5"],["Основание совмещения (RU)","личное заявление"],["Основание совмещения (KK)","жеке өтініш"]]) fireEvent.change(screen.getByLabelText(label),{target:{value}});
  vi.mocked(previewPersonnelOrderHeaderDuplicate).mockResolvedValue({blocking:false,warnings:[],candidates:[]});vi.mocked(createManualPersonnelOrderDraft).mockResolvedValue({order_id:78} as never);
  await waitFor(()=>expect(screen.getByRole("button",{name:"Создать приказ"})).toBeEnabled());fireEvent.click(screen.getByRole("button",{name:"Создать приказ"}));await waitFor(()=>expect(onCreated).toHaveBeenCalled());
  expect(createManualPersonnelOrderDraft).toHaveBeenCalledWith(expect.objectContaining({item_type_code:"CONCURRENT_DUTY_START",item_payload:{concurrent:expect.objectContaining({position_ru:"Врач",position_kk:"дәрігер",position_genitive_ru:"врача",org_unit_genitive_ru:"отделения терапии",employee_dative_ru:"Ильясовой Ассель Адиловне",rate:0.5,total_rate:1.5})}}));
});

it('shows the exact conflicting order and links directly without journal filters',async()=>{
 setup();await chooseTypeInMenu('LEAVE.ANNUAL.RECALL');await fillRecall();
 vi.mocked(previewPersonnelOrderHeaderDuplicate).mockResolvedValue({blocking:true,warnings:[],candidates:[{order_id:456,order_number:'RECALL-SLOW',order_date:'2026-10-08',status:'SIGNED',order_type_code:'HIRE',is_conflict:true,can_open:true}]});
 const button=screen.getByRole('button',{name:'Создать приказ'});await waitFor(()=>expect(button).toBeEnabled());fireEvent.click(button);
 expect(await screen.findByRole('alert')).toHaveTextContent('№ RECALL-SLOW от 08.10.2026 (ID 456)');
 expect(screen.getByRole('link',{name:/Открыть приказ/})).toHaveAttribute('href','/directory/personnel/orders?order_id=456&tab=data');
 expect(createManualPersonnelOrderDraft).not.toHaveBeenCalled();
});

it('does not send two creation requests when the same form is submitted twice',async()=>{
 setup();await chooseTypeInMenu('LEAVE.ANNUAL.RECALL');await fillRecall();
 let resolve!: (value:Awaited<ReturnType<typeof previewPersonnelOrderHeaderDuplicate>>)=>void;
 vi.mocked(previewPersonnelOrderHeaderDuplicate).mockImplementation(()=>new Promise(done=>{resolve=done;}));
 vi.mocked(createManualPersonnelOrderDraft).mockResolvedValue({order_id:789,order_number:'RECALL-SLOW'} as never);
 const button=screen.getByRole('button',{name:'Создать приказ'});await waitFor(()=>expect(button).toBeEnabled());
 fireEvent.submit(button.closest('form')!);fireEvent.submit(button.closest('form')!);expect(previewPersonnelOrderHeaderDuplicate).toHaveBeenCalledTimes(1);
 await act(async()=>resolve({blocking:false,warnings:[],candidates:[]}));await waitFor(()=>expect(createManualPersonnelOrderDraft).toHaveBeenCalledTimes(1));
});

it('keeps a successful creation when opening its card fails and prevents a retry',async()=>{
 setup(vi.fn(),()=>{throw new Error('card failed');});await chooseTypeInMenu('LEAVE.ANNUAL.RECALL');await fillRecall();
 vi.mocked(previewPersonnelOrderHeaderDuplicate).mockResolvedValue({blocking:false,warnings:[],candidates:[]});
 vi.mocked(createManualPersonnelOrderDraft).mockResolvedValue({order_id:789,order_number:'RECALL-SLOW'} as never);
 const button=screen.getByRole('button',{name:'Создать приказ'});await waitFor(()=>expect(button).toBeEnabled());fireEvent.click(button);
 expect(await screen.findByRole('alert')).toHaveTextContent('создан (ID 789)');expect(screen.getByRole('link',{name:/Открыть созданный приказ/})).toHaveAttribute('href','/directory/personnel/orders?order_id=789&tab=data');
 fireEvent.submit(button.closest('form')!);expect(createManualPersonnelOrderDraft).toHaveBeenCalledTimes(1);expect(button).toBeDisabled();
});

it("requires an explicit allowance basis and hides rates for a published replacement PAY variant", async () => {
  const variant={template_id:24,template_version_id:36,version_number:1,name_ru:"TEST замещение с доплатой",name_kk:"TEST қосымша ақы",title_ru:"TEST замещение с доплатой",title_kk:"TEST қосымша ақы",is_default:false,replacement_mode:"PAY" as const};
  vi.mocked(getPersonnelOrderPublishedVariants).mockImplementation(async code=>({items:code==="CONCURRENT_DUTY_START"?[variant]:[],independent_supported:true,creation_supported:true}));
  setup();vi.mocked(getPersonnelOrderPublishedTemplateTitle).mockResolvedValue({...variant,item_type_code:"CONCURRENT_DUTY_START"});
  await waitFor(()=>expect(screen.getByRole("button",{name:"Тип кадрового приказа"})).toBeEnabled());
  fireEvent.click(screen.getByRole("button",{name:"Тип кадрового приказа"}));
  fireEvent.change(screen.getByRole("searchbox"),{target:{value:variant.name_kk}});
  fireEvent.click(screen.getByRole("menuitem",{name:variant.name_kk}));
  await selectEmployee();
  expect(screen.queryByLabelText("Дополнительная ставка",{exact:true})).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Общая ставка",{exact:true})).not.toBeInTheDocument();
  expect(screen.getByLabelText("База расчёта доплаты (RU)",{exact:true})).toHaveValue("");
  expect(screen.getByLabelText("База расчёта доплаты (KK)",{exact:true})).toHaveValue("");
  expect(screen.getByLabelText("Срок замещения",{exact:true})).toHaveValue("");
  expect(screen.getByRole("button",{name:"Создать приказ"})).toBeDisabled();
});

it("selects only additional assignments for cessation and submits an explicit remaining total", async () => {
  const {onCreated}=setup();
  vi.mocked(getEmployee).mockResolvedValue({...employeeDetail,additional_assignments:[
    {assignment_id:1,is_primary:true,position_id:7,org_unit_id:2,rate:1,position:{name:"Директор"},org_unit:{name:"Администрация"}},
    {assignment_id:2,is_primary:false,position_id:6,org_unit_id:59,rate:0.5,position:{name:"Врач",name_kk:"дәрігер"},org_unit:{name:"Терапия",name_kk:"терапия бөлімшесінің"}},
  ]} as never);
  await chooseTypeInMenu("CONCURRENT_DUTY_END");await selectEmployee();
  expect(getEmployee).toHaveBeenCalledWith("383",true);
  const assignment=screen.getByLabelText("Прекращаемое дополнительное назначение");
  expect(assignment).toHaveValue("");expect(screen.queryByRole("option",{name:/Директор/})).not.toBeInTheDocument();
  fireEvent.change(assignment,{target:{value:"2"}});
  expect(screen.getByLabelText("Дополнительная должность (RU)")).toHaveValue("Врач");
  expect(screen.getByLabelText("Дополнительная должность (KK)")).toHaveValue("дәрігер");
  expect(screen.getByLabelText("Снимаемая ставка")).toHaveValue(0.5);
  expect(screen.getByLabelText("Оставшаяся общая ставка")).toHaveValue(null);
  for(const[label,value]of [["Номер приказа","END-TEST"],["Дата приказа","2026-07-01"],["Дата действия","2026-07-01"],["Дополнительная должность в родительном падеже (RU)","врача"],["Дополнительное подразделение в родительном падеже (RU)","отделения терапии"],["ФИО в родительном падеже (RU)","Ильясовой Ассель Адиловны"],["ФИО в исходном падеже (KK)","Ассель Адиловна Ильясовадан"],["Оставшаяся общая ставка","0.2"],["Основание прекращения совмещения (RU)","личное заявление"],["Основание прекращения совмещения (KK)","жеке өтініш"]])fireEvent.change(screen.getByLabelText(label),{target:{value}});
  vi.mocked(previewPersonnelOrderHeaderDuplicate).mockResolvedValue({blocking:false,warnings:[],candidates:[]});vi.mocked(createManualPersonnelOrderDraft).mockResolvedValue({order_id:78} as never);
  await waitFor(()=>expect(screen.getByRole("button",{name:"Создать приказ"})).toBeEnabled());fireEvent.click(screen.getByRole("button",{name:"Создать приказ"}));await waitFor(()=>expect(onCreated).toHaveBeenCalled());
  expect(createManualPersonnelOrderDraft).toHaveBeenCalledWith(expect.objectContaining({item_type_code:"CONCURRENT_DUTY_END",item_payload:{concurrent:expect.objectContaining({assignment_id:2,position_id:6,org_unit_id:59,employee_genitive_ru:"Ильясовой Ассель Адиловны",employee_ablative_kk:"Ассель Адиловна Ильясовадан",rate:0.5,remaining_rate:0.2})}}));
});
