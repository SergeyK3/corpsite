import {expect,it} from "vitest";
import {hirePositionManualForms} from "./personnelOrderHirePosition";
it('distinguishes saved manual forms from unchanged classifier forms without refreshing legacy text',()=>{
  const reference={name:'Врач',name_kk:'Дәрігер',document_nominative_ru:'врач',document_possessive_kk:'дәрігері'};
  expect(hirePositionManualForms({position_document_nominative_ru:'врач',position_document_possessive_kk:'дәрігері'},reference)).toEqual({ru:false,kk:false});
  expect(hirePositionManualForms({position_document_nominative_ru:'ручная форма',position_document_possessive_kk:'қолмен нысаны'},reference)).toEqual({ru:true,kk:true});
  expect(hirePositionManualForms({hire_position_manual_forms:{ru:true,kk:false},position_document_nominative_ru:'врач'},reference)).toEqual({ru:true,kk:false});
});
