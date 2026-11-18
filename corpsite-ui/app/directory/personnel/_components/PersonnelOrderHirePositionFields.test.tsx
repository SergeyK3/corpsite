import {useState} from "react";
import {cleanup,fireEvent,render,screen,within} from "@testing-library/react";
import {afterEach,expect,it} from "vitest";
import PersonnelOrderHirePositionFields from "./PersonnelOrderHirePositionFields";
import {renderPersonnelOrderDocument} from "./personnelOrderDocumentTemplates";
import type {PersonnelOrderDetailResponse} from "../_lib/personnelOrdersApi.client";
import approved from "../../../../../reference-data/dictionaries/positions-kk-approved-20261118.json";

const positions=[{id:7,name:'Врач',name_kk:'Дәрігер'},{id:8,name:'Эксперт',name_kk:'Сарапшы'}];
function Harness(){
  const [value,setValue]=useState<{id:number|null;ru:string;kk:string}>({id:null,ru:'',kk:''});
  return <><PersonnelOrderHirePositionFields value={value} positions={positions}
    onSelect={row=>setValue({id:row.id,ru:row.name,kk:row.name_kk||''})}
    onTextChange={(locale,text)=>setValue(previous=>({...previous,[locale]:text}))}/><output data-testid="value">{JSON.stringify(value)}</output></>;
}
afterEach(cleanup);
it('pairs reference selection in either language, preserves independent edits on blur and replaces titles on another explicit selection',()=>{
  render(<Harness/>);
  const ru=screen.getByRole('combobox',{name:'Должность (RU)'}),kk=screen.getByRole('combobox',{name:'Должность (KK)'});
  fireEvent.click(screen.getByRole('button',{name:'Открыть список должностей (RU)'}));
  expect(within(screen.getByRole('listbox')).getAllByRole('option').map(el=>el.textContent)).toEqual(['Врач','Эксперт']);
  fireEvent.click(screen.getByRole('option',{name:'Врач'}));
  expect(ru).toHaveValue('Врач');expect(kk).toHaveValue('Дәрігер');
  fireEvent.change(ru,{target:{value:'Врач — историческое уточнение'}});fireEvent.blur(ru);
  expect(kk).toHaveValue('Дәрігер');
  fireEvent.change(kk,{target:{value:'Дәрігер — тарихи нақтылау'}});fireEvent.blur(kk);
  expect(ru).toHaveValue('Врач — историческое уточнение');expect(JSON.parse(screen.getByTestId('value').textContent!).id).toBe(7);
  fireEvent.click(screen.getByRole('button',{name:'Открыть список должностей (KK)'}));
  expect(within(screen.getByRole('listbox')).getAllByRole('option').map(el=>el.textContent)).toEqual(['Дәрігер','Сарапшы']);
  fireEvent.click(screen.getByRole('option',{name:'Сарапшы'}));
  expect(ru).toHaveValue('Эксперт');expect(kk).toHaveValue('Сарапшы');expect(JSON.parse(screen.getByTestId('value').textContent!).id).toBe(8);
});

it('keeps Russian variants by ID and excludes unapproved Kazakh names from the KK list',()=>{
  const options=[
    {id:10,name:'Врач',name_kk:'Дәрігер'},
    {id:11,name:'Врач',name_kk:'Дәрігер-кеңесші'},
    {id:12,name:'Бухгалтер',name_kk:null},
  ];
  function Variants(){
    const [value,setValue]=useState<{id:number|null;ru:string;kk:string}>({id:null,ru:'',kk:''});
    return <><PersonnelOrderHirePositionFields value={value} positions={options}
      onSelect={row=>setValue({id:row.id,ru:row.name,kk:row.name_kk||''})}
      onTextChange={(locale,text)=>setValue(previous=>({...previous,[locale]:text}))}/>
      <output data-testid="variant-value">{JSON.stringify(value)}</output></>;
  }
  render(<Variants/>);
  fireEvent.click(screen.getByRole('button',{name:'Открыть список должностей (RU)'}));
  const ruOptions=within(screen.getByRole('listbox')).getAllByRole('option');
  expect(ruOptions).toHaveLength(3);
  fireEvent.click(ruOptions[1]);
  expect(JSON.parse(screen.getByTestId('variant-value').textContent!)).toEqual({id:11,ru:'Врач',kk:'Дәрігер-кеңесші'});
  fireEvent.click(screen.getByRole('button',{name:'Открыть список должностей (KK)'}));
  expect(within(screen.getByRole('listbox')).getAllByRole('option').map(el=>el.textContent)).toEqual(['Дәрігер','Дәрігер-кеңесші']);
  fireEvent.click(screen.getByRole('option',{name:'Дәрігер'}));
  expect(JSON.parse(screen.getByTestId('variant-value').textContent!)).toEqual({id:10,ru:'Врач',kk:'Дәрігер'});
  fireEvent.click(screen.getByRole('button',{name:'Открыть список должностей (RU)'}));
  fireEvent.click(screen.getByRole('option',{name:'Бухгалтер'}));
  expect(JSON.parse(screen.getByTestId('variant-value').textContent!)).toEqual({id:12,ru:'Бухгалтер',kk:''});
  expect(within(screen.getByTestId('hire-position-fields')).getByRole('status')).toHaveTextContent('нет утверждённого названия KK');
});

it('offers all 28 newly approved KK titles, pairs every RU choice by ID, and uses each KK title in the HIRE preview',()=>{
  const options=approved.items.map(row=>({id:row.position_id,name:row.name,name_kk:row.name_kk}));
  function Approved(){
    const [value,setValue]=useState<{id:number|null;ru:string;kk:string}>({id:null,ru:'',kk:''});
    return <><PersonnelOrderHirePositionFields value={value} positions={options}
      onSelect={row=>setValue({id:row.id,ru:row.name,kk:row.name_kk||''})}
      onTextChange={(locale,text)=>setValue(previous=>({...previous,[locale]:text}))}/>
      <output data-testid="approved-value">{JSON.stringify(value)}</output></>;
  }
  render(<Approved/>);
  fireEvent.click(screen.getByRole('button',{name:'Открыть список должностей (KK)'}));
  expect(within(screen.getByRole('listbox')).getAllByRole('option').map(el=>el.textContent)).toEqual(approved.items.map(row=>row.name_kk));
  for(const [index,row] of approved.items.entries()){
    fireEvent.click(screen.getByRole('button',{name:'Открыть список должностей (RU)'}));
    fireEvent.click(within(screen.getByRole('listbox')).getAllByRole('option')[index]);
    expect(JSON.parse(screen.getByTestId('approved-value').textContent!)).toEqual({id:row.position_id,ru:row.name,kk:row.name_kk});
    const detail={order:{order_id:1,order_number:'1',order_date:'2026-11-18',order_type_code:'HIRE',order_class:'PERSONNEL',status:'DRAFT',source_mode:'DIGITAL',created_by:1,storage_json:{}},
      localized_texts:[],items:[{item_id:1,order_id:1,item_number:1,item_type_code:'HIRE',item_status:'ACTIVE',employee_id:null,effective_date:'2026-11-18',payload:{source_employee_name:'Тестовый сотрудник',to_assignment:{position:{ru:row.name,kk:row.name_kk},unit:{ru:'Тестовый отдел',kk:'Сынақ бөлімі'},rate:'1.0'}}}],attachments:[],prints:[],events:[]} as unknown as PersonnelOrderDetailResponse;
    expect(renderPersonnelOrderDocument(detail,'kk')?.points[0].text).toContain(row.name_kk);
  }
});
