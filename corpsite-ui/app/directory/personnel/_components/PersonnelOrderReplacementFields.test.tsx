import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import {afterEach,expect,it,vi} from "vitest";
import {useState} from "react";
import PersonnelOrderReplacementFields,{blankReplacement,replacementBlockers,type ReplacementFields} from "./PersonnelOrderReplacementFields";
import {getEmployee,getEmployees} from "@/app/directory/employees/_lib/api.client";

vi.mock("@/app/directory/employees/_lib/api.client",()=>({getEmployee:vi.fn(),getEmployees:vi.fn(),getPositions:vi.fn().mockResolvedValue({items:[],total:0})}));
vi.mock("@/lib/api",()=>({apiFetchJson:vi.fn().mockResolvedValue({items:[]})}));
afterEach(()=>{cleanup();vi.clearAllMocks();});

it('does not require empty replaced placement or stale case forms for the service area contract',()=>{
 const worker={...blankReplacement(),employee_id:2,employee_name_ru:'Иванов Иван Иванович',employee_name_kk:'Иван Иванович Иванов',employee_genitive_ru:'Иванова Ивана Ивановича',employee_genitive_kk:'Иван Иванович Ивановтың',allowance_percent:'25'};
 for(const term_type of ['NONE','DATE','UNTIL_RETURN'] as const)expect(replacementBlockers({...worker,term_type,end_date:term_type==='DATE'?'2026-07-31':''},'PAY','2026-07-03',true,true)).toEqual([]);
 expect(replacementBlockers({...worker,term_type:'DATE'},'PAY','2026-07-03',true,true).join(' ')).toContain('Дата окончания');
});

it('offers active assignments, fills the chosen placement, and preserves manual corrections',async()=>{
 const assignments=[{assignment_id:11,position_id:6,org_unit_id:42,rate:'1',is_primary:true,position:{name:'Врач',name_kk:'дәрігер'},org_unit:{name:'Отделение терапии',name_kk:'терапия бөлімшесі'}},{assignment_id:12,position_id:7,org_unit_id:43,rate:'0.25',is_primary:false,position:{name:'Медицинская сестра',document_possessive_kk:'мейіргері'},org_unit:{name:'Отделение хирургии',document_genitive_kk:'хирургия бөлімшесінің'}}];
 const person={id:'2',fio:'Иванов Иван Иванович',first_name:'Иван',middle_name:'Иванович',last_name:'Иванов',position:{id:6,name:'Врач'},org_unit:{unit_id:42,name:'Терапия'},assignments};
 vi.mocked(getEmployees).mockResolvedValue({items:[person],total:1} as never);vi.mocked(getEmployee).mockResolvedValue(person as never);
 function Form(){const[value,setValue]=useState<ReplacementFields>(blankReplacement);return <PersonnelOrderReplacementFields value={value} onChange={setValue} mode='PAY' start='2026-07-03' orgUnits={[]} fixedAllowance serviceArea/>;}
 render(<Form/>);fireEvent.change(screen.getByLabelText('Замещаемый сотрудник (RU)'),{target:{value:'Иванов'}});fireEvent.click(await screen.findByRole('option',{name:/Иванов Иван Иванович/}));
 const select=await screen.findByLabelText('Назначение замещаемого сотрудника');expect(getEmployee).toHaveBeenCalledWith('2',true);
 expect(screen.getByLabelText('Замещаемая должность (RU)')).toHaveValue('');
 fireEvent.change(select,{target:{value:'12'}});expect(screen.getByLabelText('Замещаемая должность (RU)')).toHaveValue('Медицинская сестра');
 expect(screen.getByLabelText('Замещаемая должность в родительном падеже (RU)')).toHaveValue('медицинской сестры');
 expect(screen.getByLabelText('Замещаемое подразделение в родительном падеже (RU)')).toHaveValue('отделения хирургии');
 expect(screen.getByLabelText('Замещаемая должность (KK)')).toHaveValue('мейіргері');
 fireEvent.change(screen.getByLabelText('Замещаемая должность в родительном падеже (RU)'),{target:{value:'ручной формы'}});
 fireEvent.change(select,{target:{value:'11'}});expect(screen.getByLabelText('Замещаемая должность (RU)')).toHaveValue('Врач');expect(screen.getByLabelText('Замещаемая должность в родительном падеже (RU)')).toHaveValue('ручной формы');
 fireEvent.change(screen.getByLabelText('Замещаемое подразделение (RU)'),{target:{value:'Отделение хирургии'}});
 await waitFor(()=>expect(screen.getByLabelText('Замещаемое подразделение в родительном падеже (RU)')).toHaveValue('отделения хирургии'));
 fireEvent.change(screen.getByLabelText('Замещаемая должность (KK)'),{target:{value:''}});fireEvent.change(select,{target:{value:'12'}});expect(screen.getByLabelText('Замещаемая должность (KK)')).toHaveValue('');
});

it('leaves missing appointment details and translations empty without requiring their cases',async()=>{
 const person={id:'2',fio:'Иванов Иван Иванович',first_name:'Иван',middle_name:'Иванович',last_name:'Иванов',position:null,org_unit:null,assignments:[{assignment_id:11,position_id:6,org_unit_id:42,rate:'1',is_primary:true,position:{name:'Врач'},org_unit:{}}]};
 vi.mocked(getEmployees).mockResolvedValue({items:[person],total:1} as never);vi.mocked(getEmployee).mockResolvedValue(person as never);
 function Form(){const[value,setValue]=useState<ReplacementFields>({...blankReplacement(),allowance_percent:'50',term_type:'NONE' as const});return <><PersonnelOrderReplacementFields value={value} onChange={setValue} mode='PAY' start='2026-07-03' orgUnits={[]} fixedAllowance serviceArea/><output data-testid="blockers">{replacementBlockers(value,'PAY','2026-07-03',true,true).join(' ')}</output></>;}
 render(<Form/>);fireEvent.change(screen.getByLabelText('Замещаемый сотрудник (RU)'),{target:{value:'Иванов'}});fireEvent.click(await screen.findByRole('option',{name:/Иванов Иван Иванович/}));
 await waitFor(()=>expect(screen.getByLabelText('Замещаемая должность (RU)')).toHaveValue('Врач'));
 expect(screen.getByLabelText('Замещаемая должность в родительном падеже (RU)')).toHaveValue('врача');
 for(const label of ['Замещаемая должность (KK)','Замещаемое подразделение (RU)','Замещаемое подразделение (KK)','Замещаемое подразделение в родительном падеже (RU)'])expect(screen.getByLabelText(label)).toHaveValue('');
 expect(screen.getByTestId('blockers').textContent).toBe('');
});

it('keeps no-term distinct from unset and requires a replaced employee only for return',()=>{
 const data={...blankReplacement(),allowance_percent:'25',term_type:'NONE' as const};
 expect(replacementBlockers(data,'PAY','2026-06-15',true,true)).toEqual([]);
 expect(replacementBlockers({...data,term_type:''},'PAY','2026-06-15',true,true).join(' ')).toContain('Срок замещения');
 expect(replacementBlockers({...data,term_type:'DATE',end_date:'2026-06-30'},'PAY','2026-06-15',true,true)).toEqual([]);
 expect(replacementBlockers({...data,term_type:'UNTIL_RETURN'},'PAY','2026-06-15',true,true).join(' ')).toContain('Замещаемый сотрудник');
 function Form(){const[value,setValue]=useState<ReplacementFields>(blankReplacement);return <PersonnelOrderReplacementFields value={value} onChange={setValue} mode='PAY' start='2026-06-15' orgUnits={[]} fixedAllowance serviceArea/>;}
 render(<Form/>);expect(screen.getByRole('option',{name:'Без указания срока'})).toHaveValue('NONE');
 expect(screen.queryByLabelText('База расчёта доплаты (RU)')).not.toBeInTheDocument();expect(screen.queryByLabelText('База расчёта доплаты (KK)')).not.toBeInTheDocument();
 fireEvent.change(screen.getByLabelText('Срок замещения'),{target:{value:'NONE'}});expect(screen.queryByLabelText('Дата окончания замещения')).not.toBeInTheDocument();
});

it("offers only +25% and +50% for the selected fixed allowance contract",()=>{
  function Form(){const[value,setValue]=useState<ReplacementFields>(blankReplacement);return <PersonnelOrderReplacementFields value={value} onChange={setValue} mode="PAY" start="2026-07-03" orgUnits={[]} fixedAllowance/>;}
  render(<Form/>);
  const allowance=screen.getByRole('combobox',{name:'Доплата'});
  expect(Array.from(allowance.querySelectorAll('option')).map(o=>o.value)).toEqual(['','25','50']);
  expect(screen.queryByLabelText('Процент доплаты')).not.toBeInTheDocument();
  expect(screen.getByLabelText('База расчёта доплаты (RU)')).toHaveValue('');
  expect(screen.getByLabelText('База расчёта доплаты (KK)')).toHaveValue('');
  fireEvent.change(allowance,{target:{value:'50'}});expect(allowance).toHaveValue('50');
  expect(replacementBlockers({...blankReplacement(),allowance_percent:'75'},'PAY','2026-07-03',true).join(' ')).toContain('Выберите доплату +25% или +50%');
});

it("requires a bilingual allowance basis and never supplies financial defaults",()=>{
  const empty=blankReplacement();expect(empty.allowance_basis_ru).toBe("");expect(empty.allowance_basis_kk).toBe("");expect(empty.term_type).toBe("");
  expect(replacementBlockers(empty,"PAY","2026-07-03").join(" ")).toContain("База расчёта доплаты (RU)");
  expect(replacementBlockers(empty,"PAY","2026-07-03").join(" ")).toContain("База расчёта доплаты (KK)");
  expect(replacementBlockers(empty,"RATE","2026-07-03").join(" ")).not.toContain("База расчёта доплаты");
});

it("uses employee search to fill the replaced placement and keeps forms editable",async()=>{
  const person={id:"2",fio:"Иванов Иван Иванович",first_name:"Иван",middle_name:"Иванович",last_name:"Иванов",position:{id:6,name:"Врач",document_possessive_kk:"дәрігері"},org_unit:{unit_id:59,name:"Терапия",document_genitive_kk:"терапия бөлімшесінің"}};
  vi.mocked(getEmployees).mockResolvedValue({items:[person],total:1} as never);vi.mocked(getEmployee).mockResolvedValue(person as never);
  function Form(){const[value,setValue]=useState<ReplacementFields>(blankReplacement);return <PersonnelOrderReplacementFields value={value} onChange={setValue} mode="PAY" start="2026-07-03" orgUnits={[]}/>;}
  render(<Form/>);fireEvent.change(screen.getByLabelText("Замещаемый сотрудник (RU)"),{target:{value:"Иванов"}});
  fireEvent.click(await screen.findByRole("option",{name:/Иванов Иван Иванович/}));
  await waitFor(()=>expect(screen.getByLabelText("Замещаемая должность (KK)")).toHaveValue("дәрігері"));
  expect(screen.getByLabelText("Замещаемое подразделение (KK)")).toHaveValue("терапия бөлімшесінің");
  expect(screen.getByLabelText("ФИО замещаемого в родительном падеже (RU)")).toHaveValue("Иванова Ивана Ивановича");
  expect(screen.getByLabelText("ФИО замещаемого в родительном падеже (KK)")).toHaveValue("Иван Иванович Ивановтың");
  fireEvent.change(screen.getByLabelText("ФИО замещаемого в родительном падеже (KK)"),{target:{value:"Ручное уточнение"}});
  expect(screen.getByLabelText("ФИО замещаемого в родительном падеже (KK)")).toHaveValue("Ручное уточнение");
  expect(screen.queryByLabelText("Дополнительная ставка")).not.toBeInTheDocument();expect(screen.queryByLabelText("Общая ставка")).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Срок замещения"),{target:{value:"UNTIL_RETURN"}});expect(screen.queryByLabelText("Дата окончания замещения")).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Срок замещения"),{target:{value:"DATE"}});expect(screen.getByLabelText("Дата окончания замещения")).toHaveValue("");
});
