import {useState} from "react";
import {cleanup, fireEvent, render, screen, waitFor, within} from "@testing-library/react";
import {afterEach, expect, it, vi} from "vitest";
import {apiFetchJson} from "@/lib/api";
import PersonnelOrderHireDetailsFields from "./PersonnelOrderHireDetailsFields";
import {emptyHireDetails, type HireDetails} from "../_lib/personnelOrderHireDetails";
import {buildItemPayload, itemPayloadDraftFromRecord as payloadToDraft} from "../_lib/personnelOrderPayload";

it('selects one certificate specialty, keeps paired snapshot titles and allows an empty date or certificate',async()=>{
  vi.mocked(apiFetchJson).mockImplementation(async path=>path==='/directory/medical-specialties'?{
    items:[{medical_specialty_id:7,name:'Терапия TEST',name_kk:'Терапия KK TEST',is_active:true}],total:1
  }:{schema_ready:true,items:[]} as never);
  const view=render(<Harness/>);
  expect(screen.getByLabelText('Дата выдачи сертификата')).toHaveValue('');
  const picker=screen.getByRole('combobox',{name:'Специальность сертификата (RU)'});
  fireEvent.focus(picker);
  fireEvent.click(await screen.findByRole('option',{name:'Терапия TEST'}));
  fireEvent.change(screen.getByLabelText('Дата выдачи сертификата'),{target:{value:'2026-02-02'}});
  const details=JSON.parse(screen.getByTestId('details').textContent!);
  expect(details.certificate).toEqual({specialty:{medical_specialty_id:7,name_ru:'Терапия TEST',name_kk:'Терапия KK TEST'},issued_on:'2026-02-02',name_ru:'Терапия TEST',name_kk:'Терапия KK TEST'});
  const restored=payloadToDraft(JSON.parse(JSON.stringify(buildItemPayload('HIRE',{hire_details:details})))).hire_details!;
  view.unmount();render(<Harness initial={restored}/>);
  expect(screen.getByLabelText('Дата выдачи сертификата')).toHaveValue('2026-02-02');
  expect(screen.getByRole('combobox',{name:'Специальность сертификата (RU)'})).toHaveValue('Терапия TEST');
  expect(screen.getByRole('combobox',{name:'Специальность сертификата (KK)'})).toHaveValue('Терапия KK TEST');
  fireEvent.change(screen.getByLabelText('Дата выдачи сертификата'),{target:{value:''}});
  expect(JSON.parse(screen.getByTestId('details').textContent!).certificate.issued_on).toBe('');
  for(const locale of ['RU','KK'])fireEvent.change(screen.getByRole('combobox',{name:`Специальность сертификата (${locale})`}),{target:{value:''}});
  expect(JSON.parse(screen.getByTestId('details').textContent!).certificate).toEqual({specialty:details.certificate.specialty,issued_on:'',name_ru:'',name_kk:''});
});

it('allows historical certificate names without a dictionary choice and preserves explicit names after reopening',async()=>{
  vi.mocked(apiFetchJson).mockResolvedValue({schema_ready:true,items:[],total:0});
  const view=render(<Harness/>);
  fireEvent.change(screen.getByLabelText('Специальность сертификата (RU)'),{target:{value:'Лучевая диагностика'}});
  fireEvent.change(screen.getByLabelText('Специальность сертификата (KK)'),{target:{value:'Сәулелік диагностика'}});
  const details=JSON.parse(screen.getByTestId('details').textContent!);
  expect(details.certificate).toMatchObject({specialty:null,name_ru:'Лучевая диагностика',name_kk:'Сәулелік диагностика'});
  const restored=payloadToDraft(buildItemPayload('HIRE',{hire_details:details})).hire_details;
  view.unmount();render(<Harness initial={restored}/>);
  expect(screen.getByLabelText('Специальность сертификата (RU)')).toHaveValue('Лучевая диагностика');
  expect(screen.getByLabelText('Специальность сертификата (KK)')).toHaveValue('Сәулелік диагностика');
  expect(screen.queryByRole('combobox',{name:'Медицинская специальность (необязательно)'})).not.toBeInTheDocument();
});

vi.mock("@/lib/api", () => ({apiFetchJson: vi.fn()}));
it('opens the full dictionary with permanent arrows without replacing manual text, and reopens a focused input',async()=>{
  const rows=[{medical_specialty_id:41,name:'Радиология',name_kk:'Радиология',is_active:true},
    {medical_specialty_id:7,name:'Терапия',name_kk:'Жалпы терапия',is_active:true}];
  vi.mocked(apiFetchJson).mockImplementation(async path=>path==='/directory/medical-specialties'?{items:rows,total:2}:{schema_ready:true,items:[]} as never);
  render(<Harness/>);
  const ru=screen.getByRole('combobox',{name:'Специальность сертификата (RU)'});
  const kk=screen.getByRole('combobox',{name:'Специальность сертификата (KK)'});
  for(const locale of ['RU','KK'])expect(screen.getByRole('button',{name:`Открыть список специальностей (${locale})`})).toBeVisible();
  fireEvent.click(screen.getByRole('button',{name:'Открыть список специальностей (RU)'}));
  await screen.findByRole('option',{name:'Терапия',exact:true});
  expect(ru).toHaveValue('');
  expect(within(screen.getByRole('listbox')).getAllByRole('option')).toHaveLength(2);
  expect(screen.getByRole('listbox').parentElement).toBe(document.body);
  fireEvent.change(ru,{target:{value:'Лучевая диагностика'}});
  expect(screen.getByText('Совпадений нет. Можно сохранить введённое название')).toBeVisible();
  fireEvent.blur(ru);
  expect(ru).toHaveValue('Лучевая диагностика');expect(kk).toHaveValue('');
  fireEvent.click(screen.getByRole('button',{name:'Открыть список специальностей (KK)'}));
  expect(screen.getByRole('option',{name:'Жалпы терапия'})).toBeVisible();
  expect(ru).toHaveValue('Лучевая диагностика');
  fireEvent.click(screen.getByRole('option',{name:'Радиология'}));
  expect(ru).toHaveValue('Радиология');expect(kk).toHaveValue('Радиология');
  fireEvent.change(ru,{target:{value:'Радиология — уточнение'}});
  fireEvent.keyDown(ru,{key:'Escape'});
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
  fireEvent.click(ru);
  expect(screen.getByRole('listbox')).toBeVisible();
  expect(ru).toHaveValue('Радиология — уточнение');expect(kk).toHaveValue('Радиология');
});
it('searches both languages and supplied aliases in either editable combo, retains edits and source, and replaces both only on selection', async()=>{
  const rows=[
    {medical_specialty_id:41,name:'Радиология',name_kk:'Радиология',is_active:true,search_aliases:['лучевая диагностика']},
    {medical_specialty_id:7,name:'Терапия TEST',name_kk:'Жалпы терапия',is_active:true}
  ];
  vi.mocked(apiFetchJson).mockImplementation(async path=>path==='/directory/medical-specialties'?{items:rows,total:2}:{schema_ready:true,items:[]} as never);
  const view=render(<Harness/>);
  const ru=screen.getByRole('combobox',{name:'Специальность сертификата (RU)'});
  const kk=screen.getByRole('combobox',{name:'Специальность сертификата (KK)'});
  await waitFor(()=>expect(screen.queryByText('Загружаются специальности…')).not.toBeInTheDocument());
  for(const input of [ru,kk]){
    for(const query of ['РАДИол','ДИАГНОСТИКА луч','терапия жалпы']){
      fireEvent.change(input,{target:{value:query}});
      expect(within(screen.getByRole('listbox')).getAllByRole('option')).toHaveLength(1);
    }
    fireEvent.change(input,{target:{value:''}});
    expect(within(screen.getByRole('listbox')).getAllByRole('option')).toHaveLength(2);
  }
  fireEvent.change(kk,{target:{value:'Радиология'}});
  fireEvent.click(screen.getByRole('option',{name:'Радиология'}));
  expect(ru).toHaveValue('Радиология'); expect(kk).toHaveValue('Радиология');
  fireEvent.change(ru,{target:{value:'Лучевая диагностика (по сертификату)'}});
  fireEvent.blur(ru);
  fireEvent.change(kk,{target:{value:'Сәулелік диагностика — тарихи атау'}});
  fireEvent.keyDown(kk,{key:'Escape'});
  const details=JSON.parse(screen.getByTestId('details').textContent!);
  expect(details.certificate).toMatchObject({specialty:{medical_specialty_id:41,name_ru:'Радиология',name_kk:'Радиология'},name_ru:'Лучевая диагностика (по сертификату)',name_kk:'Сәулелік диагностика — тарихи атау'});
  const restored=payloadToDraft(buildItemPayload('HIRE',{hire_details:details})).hire_details;
  view.unmount();render(<Harness initial={restored}/>);
  expect(screen.getByRole('combobox',{name:'Специальность сертификата (RU)'})).toHaveValue(details.certificate.name_ru);
  const reopened=screen.getByRole('combobox',{name:'Специальность сертификата (KK)'});
  expect(reopened).toHaveValue(details.certificate.name_kk);
  fireEvent.change(reopened,{target:{value:'ЖАЛПЫ'}});
  fireEvent.click(await screen.findByRole('option',{name:'Жалпы терапия'}));
  expect(screen.getByRole('combobox',{name:'Специальность сертификата (RU)'})).toHaveValue('Терапия TEST');
  expect(reopened).toHaveValue('Жалпы терапия');
  fireEvent.change(reopened,{target:{value:'ТЕРАПИЯ'}});
  expect(within(screen.getByRole('listbox')).getByRole('option')).toHaveTextContent(/^Жалпы терапия$/);
  expect(screen.queryByRole('option',{name:'Терапия TEST / Жалпы терапия'})).not.toBeInTheDocument();
  fireEvent.blur(reopened);
  fireEvent.focus(screen.getByRole('combobox',{name:'Специальность сертификата (RU)'}));
  expect(within(screen.getByRole('listbox')).getByRole('option')).toHaveTextContent(/^Терапия TEST$/);
});
afterEach(() => {cleanup(); vi.mocked(apiFetchJson).mockReset();});
function Harness({initial = emptyHireDetails()}: {initial?: HireDetails}) {
  const [value, onChange] = useState(initial);
  return <><PersonnelOrderHireDetailsFields value={value} onChange={onChange}/><output data-testid="details">{JSON.stringify(value)}</output></>;
}
it("starts empty, selects paired classifier titles and roundtrips one decimal year value in HIRE only", async () => {
  vi.mocked(apiFetchJson).mockImplementation(async path=>path==='/api/ppr/education-levels'?{schema_ready: true, items: [{code: "HIGHER", name_ru: "Высшее", name_kk: "Жоғары", is_active: true}]}:{items:[],total:0} as never);
  const view = render(<Harness/>);
  expect(screen.queryByText('Образование, сертификат и трудовой стаж (необязательно)')).not.toBeInTheDocument();
  expect(screen.getByRole('combobox', {name: 'Образование / Білімі'})).toHaveValue('');
  expect(screen.getByLabelText('Трудовой стаж, лет')).toHaveValue('');
  expect(screen.queryByLabelText('Трудовой стаж (RU)')).not.toBeInTheDocument();
  expect(screen.queryByLabelText('Еңбек өтілі (KK)')).not.toBeInTheDocument();
  await screen.findByRole('option', {name: 'Высшее / Жоғары'});
  fireEvent.change(screen.getByRole('combobox', {name:'Образование / Білімі'}), {target: {value: 'HIGHER'}});
  fireEvent.change(screen.getByLabelText('Трудовой стаж, лет'), {target: {value: '17.3'}});
  expect(screen.getByLabelText('Трудовой стаж, лет')).toHaveValue('17,3');
  const details = JSON.parse(screen.getByTestId('details').textContent!);
  expect(details.education).toEqual({code: 'HIGHER', ru: 'Высшее', kk: 'Жоғары'});
  const payload = buildItemPayload('HIRE', {hire_details: details});
  expect(payloadToDraft(JSON.parse(JSON.stringify(payload))).hire_details).toEqual({...details, service_length_years:'17.3'});
  expect(buildItemPayload('TRANSFER', {hire_details: details})).not.toHaveProperty('hire_details');
  view.unmount(); render(<Harness initial={payloadToDraft(payload).hire_details}/>);
  expect(screen.getByLabelText('Трудовой стаж, лет')).toHaveValue('17,3');
  await waitFor(() => expect(screen.getByRole('combobox', {name:'Образование / Білімі'})).toHaveValue('HIGHER'));
  fireEvent.change(screen.getByRole('combobox', {name:'Образование / Білімі'}), {target: {value: ''}});
  expect(JSON.parse(screen.getByTestId('details').textContent!).education).toEqual({code:'',ru:'',kk:''});
});
it("preserves a saved classifier snapshot after rename or failure without inventing KK", async () => {
  vi.mocked(apiFetchJson).mockRejectedValue(Error('Unavailable'));
  const initial = {education: {code: 'OLD', ru: 'Сохранённое образование', kk: ''}, service_length: {ru: '', kk: ''}};
  render(<Harness initial={initial}/>);
  await screen.findByText(/Не удалось загрузить уровни образования/);
  expect(screen.getByRole('combobox', {name:'Образование / Білімі'})).toHaveValue('__saved__');
  expect(JSON.parse(screen.getByTestId('details').textContent!)).toEqual(initial);
  expect(payloadToDraft({}).hire_details).toBeUndefined();
});

it('keeps legacy prose opaque, preserves partial typing and explicitly saves zero or empty', async () => {
  vi.mocked(apiFetchJson).mockResolvedValue({schema_ready:true,items:[]});
  const initial = {education:{code:'',ru:'',kk:''}, service_length:{ru:'17 лет и 3 месяца, по архиву',kk:'Сақталған мәтін'}};
  render(<Harness initial={initial}/>);
  await waitFor(() => expect(apiFetchJson).toHaveBeenCalled());
  const input = screen.getByLabelText('Трудовой стаж, лет');
  expect(input).toHaveValue('');
  expect(screen.getByTestId('hire-legacy-tenure')).toHaveTextContent(initial.service_length.ru);
  let data = JSON.parse(screen.getByTestId('details').textContent!);
  expect(buildItemPayload('HIRE',{hire_details:data}).hire_details).not.toHaveProperty('service_length_years');
  for (const value of ['17','17,','17,3']) {
    fireEvent.change(input,{target:{value}});
    expect(input).toHaveValue(value);
  }
  fireEvent.change(input,{target:{value:'-1'}});
  expect(input).toBeInvalid();
  fireEvent.change(input,{target:{value:'0'}});
  expect(input).toBeValid();
  data = JSON.parse(screen.getByTestId('details').textContent!);
  expect(buildItemPayload('HIRE',{hire_details:data}).hire_details).toMatchObject({service_length_years:'0',service_length:initial.service_length});
  fireEvent.change(input,{target:{value:''}});
  data = JSON.parse(screen.getByTestId('details').textContent!);
  expect(buildItemPayload('HIRE',{hire_details:data}).hire_details).toMatchObject({service_length_years:'',service_length:initial.service_length});
});
