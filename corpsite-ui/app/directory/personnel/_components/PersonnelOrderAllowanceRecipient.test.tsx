import {render,screen,fireEvent,waitFor,cleanup} from '@testing-library/react';
import {afterEach,expect,it} from 'vitest';
import {useState} from 'react';
import type {EmployeeDTO} from '@/app/directory/employees/_lib/types';
import PersonnelOrderAllowanceRecipient,{blankAllowanceRecipient,recipientBlockers} from './PersonnelOrderAllowanceRecipient';
import {russianEmployeeDativeForOrder,russianEmployeeGenitiveForOrder,russianReferenceCase} from '../_lib/personnelOrderRussianWording';
const employee={id:'1',fio:'Турымов Алибек Рапхатович',last_name:'Турымов',first_name:'Алибек',middle_name:'Рапхатович',has_current_assignment:true,position:{id:6,name:'Врач',document_possessive_kk:'дәрігері'},org_unit:{unit_id:42,name:'Терапевтическое отделение',document_genitive_kk:'терапия бөлімшесінің'},assignments:[]} as unknown as EmployeeDTO;
afterEach(cleanup);
it('calculates source cases and keeps saved forms unchanged',()=>{
 expect(russianReferenceCase('Менеджер','dative')).toBe('менеджеру');
 expect(russianEmployeeDativeForOrder(employee)).toBe('Турымову Алибеку Рапхатовичу');
 expect(russianEmployeeGenitiveForOrder(employee)).toBe('Турымова Алибека Рапхатовича');
 expect(russianEmployeeDativeForOrder({...employee,document_forms_ru:{employee_full_name_dative_ru:'Сохранённому имени'}})).toBe('Сохранённому имени');
 expect(russianReferenceCase('Главная медицинская сестра','dative')).toBe('главной медицинской сестре');
 expect(russianReferenceCase('Отделение терапии','genitive')).toBe('отделения терапии');
 expect(russianReferenceCase('Гинекология','genitive')).toBe('гинекологии');
 expect(russianReferenceCase('Акушерка','dative')).toBe('акушерке');
 expect(russianReferenceCase('Сестра-хозяйка','genitive')).toBe('сестры-хозяйки');
 expect(russianReferenceCase('Неизвестный код','genitive')).toBe('');
});

it('does not require a manual dative even when the automatic declension is unavailable',()=>{
 const value={...blankAllowanceRecipient(),assignment_id:749,position_ru:'Неизвестный код',position_kk:'менеджері',org_unit_ru:'Отдел кадров',org_unit_kk:'кадрлар бөлімінің',org_unit_genitive_ru:'отдела кадров'};
 expect(recipientBlockers(value,employee)).toEqual([]);
});

it('autofills the manager appointment without editing or confirming the dative',async()=>{
 const manager={...employee,id:'771',fio:'Хамитжанова Куралай Данабековна',position:{id:29,name:'Менеджер',job_nameru:'Менеджер',job_namekk_doc:'менеджері'},org_unit:{unit_id:73,name:'Отдел кадров',name_kk:'Кадрлар бөлімі'},assignments:[{assignment_id:749,position_id:29,org_unit_id:73,rate:'1',is_primary:true,position:{name:'Менеджер'},org_unit:{name:'Отдел кадров',name_kk:'Кадрлар бөлімі'}}]} as unknown as EmployeeDTO;
 function Form(){const[value,setValue]=useState(blankAllowanceRecipient);return <><PersonnelOrderAllowanceRecipient employee={manager} value={value} onChange={setValue}/><output>{recipientBlockers(value,manager).join(' ')}</output></>;}
 render(<Form/>);await waitFor(()=>expect(screen.getByLabelText('Должность получателя в дательном падеже (RU)')).toHaveValue('менеджеру'));
 expect(screen.getByLabelText('Должность получателя (KK)')).toHaveValue('менеджері');expect(screen.getByRole('status').textContent).toBe('');
});

it('updates calculated recipient cases when the source is refined and preserves a manual case',async()=>{
 function Form(){const[value,setValue]=useState(blankAllowanceRecipient);return <PersonnelOrderAllowanceRecipient employee={employee} value={value} onChange={setValue}/>;}
 render(<Form/>);await waitFor(()=>expect(screen.getByLabelText('Должность получателя в дательном падеже (RU)')).toHaveValue('врачу'));
 fireEvent.change(screen.getByLabelText('Должность получателя (RU)'),{target:{value:'Акушерка'}});
 await waitFor(()=>expect(screen.getByLabelText('Должность получателя в дательном падеже (RU)')).toHaveValue('акушерке'));
 fireEvent.change(screen.getByLabelText('Должность получателя в дательном падеже (RU)'),{target:{value:'ручной форме'}});
 fireEvent.change(screen.getByLabelText('Должность получателя (RU)'),{target:{value:'Медицинская сестра'}});
 expect(screen.getByLabelText('Должность получателя в дательном падеже (RU)')).toHaveValue('ручной форме');
});
it('prefills a single assignment once and preserves manual corrections on reread',async()=>{
 function Form({person}:{person:EmployeeDTO}){const[value,setValue]=useState(blankAllowanceRecipient);return <PersonnelOrderAllowanceRecipient employee={person} value={value} onChange={setValue}/>;}
 const view=render(<Form person={employee}/>);await waitFor(()=>expect(screen.getByLabelText('Должность получателя в дательном падеже (RU)')).toHaveValue('врачу'));
 expect(screen.getByLabelText('Подразделение получателя для текста (RU)')).toHaveValue('терапевтического отделения');
 expect(screen.getByLabelText('Должность получателя (KK)')).toHaveValue('дәрігері');
 fireEvent.change(screen.getByLabelText('Должность получателя в дательном падеже (RU)'),{target:{value:'ручному уточнению'}});
 view.rerender(<Form person={{...employee,assignments:[]}}/>);
 expect(screen.getByLabelText('Должность получателя в дательном падеже (RU)')).toHaveValue('ручному уточнению');
});
it('requires an explicit choice among multiple assignments and takes the chosen placement',async()=>{
 const assignments=[{assignment_id:11,position_id:6,org_unit_id:42,rate:'1',is_primary:true,position:{name:'Врач',document_possessive_kk:'дәрігері'},org_unit:{name:'Терапевтическое отделение',document_genitive_kk:'терапия бөлімшесінің'}},{assignment_id:12,position_id:7,org_unit_id:43,rate:'0.25',is_primary:false,position:{name:'Медицинская сестра',document_possessive_kk:'мейіргері'},org_unit:{name:'Отделение хирургии',document_genitive_kk:'хирургия бөлімшесінің'}}];
 const person={...employee,assignments};
 function Form(){const[value,setValue]=useState(blankAllowanceRecipient);return <><PersonnelOrderAllowanceRecipient employee={person} value={value} onChange={setValue}/><output>{recipientBlockers(value,person).join(' ')}</output></>;}
 render(<Form/>);expect(screen.getByRole('combobox',{name:'Назначение получателя'})).toHaveValue('');expect(screen.getByRole('status')).toHaveTextContent('Выберите назначение');
 fireEvent.change(screen.getByRole('combobox',{name:'Назначение получателя'}),{target:{value:'12'}});
 expect(screen.getByLabelText('Должность получателя в дательном падеже (RU)')).toHaveValue('медицинской сестре');
 expect(screen.getByLabelText('Подразделение получателя для текста (RU)')).toHaveValue('отделения хирургии');
 expect(screen.getByRole('status').textContent).toBe('');
 fireEvent.change(screen.getByLabelText('Должность получателя в дательном падеже (RU)'),{target:{value:'уточнённой форме'}});
 fireEvent.change(screen.getByRole('combobox',{name:'Назначение получателя'}),{target:{value:'12'}});
 expect(screen.getByLabelText('Должность получателя в дательном падеже (RU)')).toHaveValue('уточнённой форме');
 fireEvent.change(screen.getByRole('combobox',{name:'Назначение получателя'}),{target:{value:''}});
 expect(screen.getByLabelText('Должность получателя (RU)')).toHaveValue('');
});
