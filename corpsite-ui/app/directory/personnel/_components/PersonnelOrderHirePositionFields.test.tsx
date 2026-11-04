import {useState} from "react";
import {cleanup,fireEvent,render,screen,within} from "@testing-library/react";
import {afterEach,expect,it} from "vitest";
import PersonnelOrderHirePositionFields from "./PersonnelOrderHirePositionFields";

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
