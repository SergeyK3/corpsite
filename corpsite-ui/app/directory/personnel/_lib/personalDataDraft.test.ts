import {expect,it} from 'vitest';
import {emptyPersonalDataDraft,personalDataErrors,personalDataOrderPayload,personalDataDraftFromRecord} from './personalDataDraft';
import {buildItemPayload,itemPayloadDraftFromRecord} from './personnelOrderPayload';
it('omits server-only manual-subject metadata when reopening a personal-data item for saving',()=>{
 const saved=JSON.parse(JSON.stringify({...emptyPersonalDataDraft(),subject_mode:'MANUAL',source_employee_name:'TEST',unresolved_subject:{full_name:'TEST',input_mode:'manual',needs_employee_link:false}}));
 expect(personalDataOrderPayload(personalDataDraftFromRecord(saved)).unresolved_subject).toEqual({full_name:'TEST'});
});
it('uses editable initial labels without overwriting saved changes or intentional blanks',()=>{
 expect(emptyPersonalDataDraft().personal_data).toEqual({changes_ru:'Фамилия',changes_kk:'Тегі'});
 expect(personalDataDraftFromRecord({personal_data:{changes_ru:'Имя TEST',changes_kk:''}}).personal_data).toEqual({changes_ru:'Имя TEST',changes_kk:''});
});
it.each(['ABSENT','TO_CLARIFY'] as const)('round-trips %s separately from an empty identity date',status=>{
 const draft=emptyPersonalDataDraft();draft.identity_document.issued_at_status=status;
 const payload=personalDataOrderPayload(draft);
 expect(payload.identity_document.issued_at).toBe('');
 expect(personalDataDraftFromRecord(itemPayloadDraftFromRecord(payload).personal_data_document!).identity_document.issued_at_status).toBe(status);
 expect(personalDataErrors(draft).some(error=>error.includes('Дата выдачи'))).toBe(false);
});
it('saves personal-data changes and identity details as an independent round-trip snapshot',()=>{
 const draft=emptyPersonalDataDraft();Object.assign(draft,{subject_mode:'MANUAL',source_employee_name:'TEST',effective_date:'2026-11-01'});
 draft.document_forms_ru={employee_full_name_genitive_ru:'TEST RU',position_document_genitive_ru:'TEST RU JOB'};
 draft.document_forms_kk={employee_full_name_genitive_kk:'TEST KK',position_document_possessive_kk:'TEST KK JOB'};
 draft.document_org_unit={unit_id:7,name:'TEST',name_kk:'TEST',document_genitive_ru:'TEST UNIT RU',document_genitive_kk:'TEST UNIT KK'};
 draft.personal_data={changes_ru:'Имя TEST',changes_kk:'Аты TEST',new_full_name_ru:'Новое ФИО TEST RU',new_full_name_kk:'Жаңа Аты TEST KK',new_surname_ru:'Новая Фамилия',new_given_name_ru:'Юлия',new_surname_kk:'Жаңа Тегі',new_given_name_kk:'Әлия'};Object.assign(draft.identity_document,{number:'TEST-ID',issued_at:'2026-10-01'});
 expect(personalDataErrors(draft)).toEqual([]);
 const payload=personalDataOrderPayload(draft);expect(payload.employee_id).toBeNull();
 expect(payload.unresolved_subject).toEqual({full_name:'TEST'});
 expect(buildItemPayload('PERSONAL_DATA_CHANGE',itemPayloadDraftFromRecord(payload))).toEqual(payload);
 expect(personalDataDraftFromRecord(JSON.parse(JSON.stringify(payload))).personal_data).toEqual(draft.personal_data);
 expect(payload).not.toHaveProperty('education');expect(payload).not.toHaveProperty('education_document');
});
it('requires subject, bilingual changes, saved forms and real complete identity/effective dates',()=>{
 const draft=emptyPersonalDataDraft();expect(personalDataErrors(draft).length).toBeGreaterThan(0);
 draft.effective_date='2026-02-30';draft.identity_document.issued_at='2026-13-01';
 expect(personalDataErrors(draft).filter(error=>error.includes('полную дату'))).toHaveLength(2);
});
