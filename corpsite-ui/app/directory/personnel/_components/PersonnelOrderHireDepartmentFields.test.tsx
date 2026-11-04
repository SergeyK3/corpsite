import {useState} from "react";
import {cleanup, fireEvent, render, screen, within} from "@testing-library/react";
import {afterEach, expect, it} from "vitest";
import PersonnelOrderHireDepartmentFields from "./PersonnelOrderHireDepartmentFields";
import {blankDepartment, departmentFromPayload, departmentSnapshot, type DepartmentDraft} from "../_lib/personnelOrderDepartment";

const options=[
  {unit_id:1,name:'Лучевая диагностика',name_kk:'Сәулелік диагностика',document_genitive_ru:'лучевой диагностики',document_genitive_kk:'сәулелік диагностикасының',group_id:null},
  {unit_id:2,name:'Архив',name_kk:null,document_genitive_ru:null,document_genitive_kk:null,group_id:null},
];
function Harness({initial=blankDepartment()}:{initial?:DepartmentDraft}){
  const [value,onChange]=useState(initial);
  return <><PersonnelOrderHireDepartmentFields value={value} options={options} onChange={next=>onChange(next)}/><output data-testid="value">{JSON.stringify(value)}</output></>;
}
afterEach(cleanup);
const input=(name:string)=>screen.getByRole('combobox',{name:`Подразделение (${name})`});
const saved=()=>JSON.parse(screen.getByTestId('value').textContent!) as DepartmentDraft;
it('shows all four editable fields immediately and selects the same dictionary row through either language',()=>{
  render(<Harness/>);
  const block=screen.getByTestId('document-department');
  expect(block.querySelector('select,details,summary')).toBeNull();
  expect(within(block).getAllByRole('combobox')).toHaveLength(2);
  for(const label of ['Подразделение (RU)','Подразделение (KK)','Для текста RU (родительный)','Для текста KK (ілік септік)'])expect(screen.getByLabelText(label)).toBeVisible();
  for(const locale of ['RU','KK']){
    fireEvent.click(screen.getByRole('button',{name:`Открыть список подразделений (${locale})`}));
    const list=screen.getByRole('listbox');
    expect(list.parentElement).toBe(document.body);
    expect(within(list).getAllByRole('option').map(el=>el.textContent)).toEqual(locale==='RU'?['Лучевая диагностика','Архив']:['Сәулелік диагностика','Нет названия KK']);
    fireEvent.click(within(list).getByRole('option',{name:locale==='RU'?options[0].name:options[0].name_kk!}));
    expect(input('RU')).toHaveValue(options[0].name);expect(input('KK')).toHaveValue(options[0].name_kk);
    expect(screen.getByLabelText('Для текста RU (родительный)')).toHaveValue(options[0].document_genitive_ru);
    expect(screen.getByLabelText('Для текста KK (ілік септік)')).toHaveValue(options[0].document_genitive_kk);
    expect(saved().unit?.unit_id).toBe(1);
  }
});
it('preserves independent text, forms, explicit blanks and the selected source through save and reopen',()=>{
  const view=render(<Harness/>);
  fireEvent.click(screen.getByRole('button',{name:'Открыть список подразделений (RU)'}));
  fireEvent.click(screen.getByRole('option',{name:options[0].name}));
  fireEvent.change(input('RU'),{target:{value:'Отделение по историческому приказу'}});fireEvent.blur(input('RU'));
  expect(input('KK')).toHaveValue(options[0].name_kk);expect(saved().unit?.unit_id).toBe(1);
  fireEvent.change(input('KK'),{target:{value:'Тарихи бөлімше'}});
  fireEvent.change(screen.getByLabelText('Для текста RU (родительный)'),{target:{value:'исторического отделения'}});
  fireEvent.change(screen.getByLabelText('Для текста KK (ілік септік)'),{target:{value:''}});
  const draft=saved(),snapshot=departmentSnapshot(draft);
  view.unmount();render(<Harness initial={departmentFromPayload({document_org_unit:JSON.parse(JSON.stringify(snapshot))})}/>);
  expect(saved()).toEqual(draft);
  expect(input('RU')).toHaveValue('Отделение по историческому приказу');expect(input('KK')).toHaveValue('Тарихи бөлімше');
  expect(screen.getByLabelText('Для текста RU (родительный)')).toHaveValue('исторического отделения');
  expect(screen.getByLabelText('Для текста KK (ілік септік)')).toHaveValue('');
  fireEvent.click(screen.getByRole('button',{name:'Открыть список подразделений (KK)'}));
  fireEvent.click(screen.getByRole('option',{name:'Нет названия KK'}));
  expect(input('RU')).toHaveValue('Архив');expect(input('KK')).toHaveValue('');
  expect(screen.getByLabelText('Для текста RU (родительный)')).toHaveValue('');
  expect(screen.getByLabelText('Для текста KK (ілік септік)')).toHaveValue('');
  expect(saved().unit?.unit_id).toBe(2);
});
it('searches words in both languages without requiring selection or translating typed text',()=>{
  render(<Harness/>);
  fireEvent.change(input('KK'),{target:{value:'ДИАГНОСТИКА луч'}});
  expect(screen.getByRole('option')).toHaveTextContent('Сәулелік диагностика');
  expect(input('RU')).toHaveValue('');
  fireEvent.change(input('KK'),{target:{value:'Собственное название'}});fireEvent.blur(input('KK'));
  expect(input('KK')).toHaveValue('Собственное название');expect(input('RU')).toHaveValue('');expect(saved().unit).toBeNull();
});
