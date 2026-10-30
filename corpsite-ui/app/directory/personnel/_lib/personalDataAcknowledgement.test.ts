import {expect,it} from 'vitest';
import {personalDataAcknowledgementNames} from './personalDataAcknowledgement';
it('formats explicitly supplied compound surname and first initial independently in RU and KK',()=>{
 expect(personalDataAcknowledgementNames({personal_data:{new_full_name_ru:'НЕ РАЗБИРАТЬ ЭТУ СТРОКУ',new_full_name_kk:'АТЫ ӘКЕСІ ТЕГІ',new_surname_ru:'Новая Двойная-Фамилия',new_given_name_ru:'Юлия',new_surname_kk:'Жаңа Тегі',new_given_name_kk:'Әлия'}})).toEqual({ru:'Новая Двойная-Фамилия Ю.',kk:'Ә. Жаңа Тегі'});
});
it('uses original canonical order rather than the new full-name text',()=>{
 expect(personalDataAcknowledgementNames({source_employee_name:'Старый Иван',personal_data:{new_full_name_ru:'Новый Павел',new_surname_ru:'Новый',new_surname_kk:'Жаңа'}})).toEqual({ru:'Новый И.',kk:'И. Жаңа'});
});
it('uses unchanged structured given names when new names are empty, with localized new names taking precedence',()=>{
 const payload={source_given_name_ru:'Алексей',source_given_name_kk:'Әли',personal_data:{new_surname_ru:'Новая',new_surname_kk:'Жаңа',new_given_name_ru:'',new_given_name_kk:''}};
 expect(personalDataAcknowledgementNames(payload)).toEqual({ru:'Новая А.',kk:'Ә. Жаңа'});
 expect(personalDataAcknowledgementNames({...payload,personal_data:{...payload.personal_data,new_given_name_ru:'Юлия',new_given_name_kk:'Үміт'}})).toEqual({ru:'Новая Ю.',kk:'Ү. Жаңа'});
});
it('uses RU canonical and KK case order for manual subjects, ignores obsolete initials and prioritizes a new given name',()=>{
 const payload={source_employee_name:'Изжанова Айгерим Мукановна',document_forms_kk:{employee_full_name_genitive_kk:'Айгерим Мукановна Изжанованың'},personal_data:{new_surname_ru:'Ержанова',new_surname_kk:'Ержанова',new_given_name_ru:'',new_given_name_kk:'',acknowledgement_initial_ru:'Я',acknowledgement_initial_kk:'Я.'}};
 expect(personalDataAcknowledgementNames(payload)).toEqual({ru:'Ержанова А.',kk:'А. Ержанова'});
 expect(personalDataAcknowledgementNames({...payload,personal_data:{...payload.personal_data,new_given_name_ru:'Юлия',new_given_name_kk:'Әлия'}})).toEqual({ru:'Ержанова Ю.',kk:'Ә. Ержанова'});
});
it('supports RU and KK case-only names with different first letters and no canonical name',()=>{
 expect(personalDataAcknowledgementNames({document_forms_ru:{employee_full_name_genitive_ru:'Старой Алёны Тестовны'},document_forms_kk:{employee_full_name_genitive_kk:'Әлия Тестқызы Ескінің'},personal_data:{new_surname_ru:'Новая',new_surname_kk:'Жаңа'}})).toEqual({ru:'Новая А.',kk:'Ә. Жаңа'});
});
