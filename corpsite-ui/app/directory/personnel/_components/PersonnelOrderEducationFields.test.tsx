import { useState } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import PersonnelOrderEducationFields from "./PersonnelOrderEducationFields";
import { educationDraftFromRecord, educationErrors, educationOrderPayload, emptyEducationDraft, refreshEducationContext, type EducationDraft } from "../_lib/educationDraft";
import { resolvePersonnelDocumentContext } from "../_lib/personnelOrderDocumentContext";

vi.mock("../_lib/educationOrderCatalogs", () => ({ useEducationOrderCatalogs: () => ({
  loading: false, errors: [],
  levels: [{code:"NO_EDUCATION",name_ru:"Без образования",name_kk:"Білімі жоқ",is_active:true}],
  kinds: [{code:"SCHOOL_ATTESTATE",name_ru:"Аттестат",name_kk:"Аттестат KK",is_active:true}],
  specialties: [{code:"7",name_ru:"Терапия",name_kk:"Терапия KK",is_active:true},{code:"8",name_ru:"Без перевода",name_kk:null,is_active:true}],
  units: [{unit_id:2,name:"Отделение",name_kk:"Бөлімше",document_genitive_ru:"отделения",document_genitive_kk:"Бөлімшесінің",group_id:null}],
}) }));
vi.mock("../_lib/personnelOrderPositions", () => ({ usePersonnelOrderPositions: () => ({
  loading: false, error: false,
  positions: [{id:3,name:"Врач",name_kk:"Дәрігер",document_genitive_ru:"врача",document_possessive_kk:"дәрігері"}],
}) }));
afterEach(cleanup);
function Harness({initial=emptyEducationDraft()}:{initial?:EducationDraft}) {
  const [value,onChange]=useState(initial);
  return <><PersonnelOrderEducationFields value={value} onChange={onChange}/><output data-testid="payload">{JSON.stringify(educationOrderPayload(value))}</output></>;
}
const payload=()=>JSON.parse(screen.getByTestId('payload').textContent || '{}') as EducationDraft;

it('pairs reference fields in either language, distinguishes no selection, and never invents a specialty translation',()=>{
  render(<Harness/>);
  fireEvent.change(screen.getByLabelText('Уровень образования KK'),{target:{value:'NO_EDUCATION'}});
  expect(screen.getByLabelText('Уровень образования RU')).toHaveValue('NO_EDUCATION');
  expect(payload().education).toMatchObject({level_code:'NO_EDUCATION',level_ru:'Без образования',level_kk:'Білімі жоқ'});
  fireEvent.change(screen.getByLabelText('Уровень образования RU'),{target:{value:''}});
  expect(payload().education).toMatchObject({level_code:null,level_ru:'',level_kk:''});
  fireEvent.change(screen.getByLabelText('Специальность KK'),{target:{value:'7'}});
  expect(payload().education).toMatchObject({medical_specialty_id:7,specialty_ru:'Терапия',specialty_kk:'Терапия KK'});
  fireEvent.change(screen.getByLabelText('Специальность RU'),{target:{value:'8'}});
  expect(payload().education).toMatchObject({medical_specialty_id:8,specialty_ru:'Без перевода',specialty_kk:''});
  fireEvent.change(screen.getByLabelText('Специальность KK'),{target:{value:''}});
  expect(payload().education).toMatchObject({medical_specialty_id:null,specialty_ru:'',specialty_kk:''});
  fireEvent.change(screen.getByLabelText('Вид документа KK'),{target:{value:'SCHOOL_ATTESTATE'}});
  expect(payload().education_document).toMatchObject({kind_code:'SCHOOL_ATTESTATE',kind_ru:'Аттестат',kind_kk:'Аттестат KK'});
  expect(screen.getByLabelText('Уровень образования RU')).not.toBeRequired();
  expect(screen.getByLabelText('Специальность KK')).not.toBeRequired();
  expect(screen.getByLabelText('Вид документа RU')).toBeRequired();
});

it('fills saved position and unit cases without merging distinct KK grammatical forms',()=>{
  render(<Harness/>);
  fireEvent.click(screen.getByRole('button',{name:'Выбрать: Должность RU'}));
  fireEvent.click(screen.getByRole('option',{name:'Врач'}));
  expect(payload()).toMatchObject({source_position_name:'Врач',source_position_name_kk:'Дәрігер',document_forms_ru:{position_document_genitive_ru:'врача'},document_forms_kk:{position_document_possessive_kk:'дәрігері'}});
  fireEvent.change(screen.getByLabelText('Выбрать подразделение KK'),{target:{value:'2'}});
  expect(payload().document_org_unit).toEqual({unit_id:2,name:'Отделение',name_kk:'Бөлімше',document_genitive_ru:'отделения',document_genitive_kk:'Бөлімшесінің'});
});

it('restores exact snapshots even when labels changed or records are no longer in the catalog',()=>{
  const initial=emptyEducationDraft();
  initial.education={level_code:'NO_EDUCATION',level_ru:'Старое название',level_kk:'Сақталған атау',medical_specialty_id:99,specialty_ru:'Архивная специальность',specialty_kk:''};
  initial.education_document={kind_code:'OLD',kind_ru:'Архивный документ',kind_kk:'Мұрағат құжаты',number:'TEST',issued_at:'2026-10-01'};
  const restored=educationDraftFromRecord(JSON.parse(JSON.stringify(educationOrderPayload(initial))));
  render(<Harness initial={restored}/>);
  expect(payload().education).toEqual(initial.education);
  expect(payload().education_document).toEqual({...initial.education_document,issued_at_status:'KNOWN'});
  expect(screen.getByLabelText('Уровень образования RU')).toHaveDisplayValue('Старое название (сохранённое значение)');
  expect(screen.getByLabelText('Специальность KK')).toHaveDisplayValue('Нет названия в справочнике (сохранённое значение)');
});

it('accepts empty level and specialty without changing other required validation',()=>{
  const errors=educationErrors(emptyEducationDraft());
  expect(errors.some(error=>/Уровень образования|Специальность/.test(error))).toBe(false);
  expect(errors.some(error=>error.includes('Вид документа'))).toBe(true);
});

it('preserves selected position and department snapshots when employee context loads on reopen',()=>{
  const initial=emptyEducationDraft();
  initial.source_position_id=3;
  initial.source_position_name='Сохранённая должность';
  initial.document_org_unit={unit_id:7,name:'Сохранённое отделение',name_kk:'',document_genitive_ru:'сохранённого отделения',document_genitive_kk:''};
  const context=resolvePersonnelDocumentContext({id:9,fio:'Тест',position:{id:1,name:'Другая должность',name_kk:'Другое KK',document_possessive_kk:'Другая форма'},org_unit:{unit_id:2,name:'Другое отделение',name_kk:'Другое KK'}});
  const restored=refreshEducationContext(initial,context);
  expect(restored.source_position_name).toBe('Сохранённая должность');
  expect(restored.source_position_name_kk).toBe('');
  expect(restored.document_forms_kk.position_document_possessive_kk).toBe('');
  expect(restored.document_org_unit).toEqual(initial.document_org_unit);
});

it('stores and restores an explicit clarification state without inventing a date',()=>{
  const initial=emptyEducationDraft();
  initial.education_document.issued_at='2026-06-20';
  const view=render(<Harness initial={initial}/>);
  fireEvent.change(screen.getByLabelText('Состояние даты выдачи документа'),{target:{value:'TO_CLARIFY'}});
  expect(screen.getByLabelText('Дата выдачи документа')).toBeDisabled();
  expect(screen.getByLabelText('Дата выдачи документа')).not.toBeRequired();
  expect(payload().education_document).toMatchObject({issued_at_status:'TO_CLARIFY',issued_at:''});
  expect(educationErrors(payload()).some(error=>error.includes('дату выдачи'))).toBe(false);
  const restored=educationDraftFromRecord(JSON.parse(JSON.stringify(payload())));
  view.unmount();
  render(<Harness initial={restored}/>);
  expect(screen.getByLabelText('Состояние даты выдачи документа')).toHaveValue('TO_CLARIFY');
  expect(screen.getByLabelText('Дата выдачи документа')).toHaveValue('');
  fireEvent.change(screen.getByLabelText('Состояние даты выдачи документа'),{target:{value:'KNOWN'}});
  expect(screen.getByLabelText('Дата выдачи документа')).toBeEnabled();
  expect(screen.getByLabelText('Дата выдачи документа')).toBeRequired();
  expect(educationErrors(payload()).some(error=>error.includes('дату выдачи'))).toBe(true);
});
