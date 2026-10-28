import {expect,it} from "vitest";
import {buildItemPayload,itemPayloadDraftFromRecord} from "./personnelOrderPayload";
import {emptyCategoryDraft,generateCategoryDraft} from "./qualificationCategoryDraft";
import {getItemFormRegistry,normalizeItemFormType} from "./personnelOrderItemFormRegistry";
import {PERSONNEL_ORDER_CREATE_TYPES} from "./personnelOrderLabels";
import {buildPersonnelOrderPrintDocumentHtml} from "./personnelOrderPrintDocumentHtml";
import type {PersonnelOrderPrintViewModel} from "./personnelOrderPrintViewModel";

it("registers category in ordinary creation and editing without legacy placement/rate fields",()=>{
  expect(PERSONNEL_ORDER_CREATE_TYPES).toContain('QUALIFICATION_CATEGORY');
  expect(normalizeItemFormType('QUALIFICATION_CATEGORY')).toBe('QUALIFICATION_CATEGORY');
  expect(getItemFormRegistry('QUALIFICATION_CATEGORY')).toMatchObject({employeePicker:true,showTargetRate:false,showHirePlacement:false,backendItemType:'QUALIFICATION_CATEGORY'});
});
it("round trips classifier data and bilingual specialty snapshots",()=>{
  const payload={...emptyCategoryDraft(),contract:'medical-qualification-category-v2',effective_date:'2026-07-01',employee_id:900001,source_employee_name:'TEST',medical_specialty:{medical_specialty_id:900003,name_ru:'Терапия',name_kk:'Терапия'},qualification_category:{code:3,name_ru:'Первая категория',name_kk:'Бірінші санат',assigned_at:'2026-06-11'}};
  expect(buildItemPayload('QUALIFICATION_CATEGORY',itemPayloadDraftFromRecord(payload))).toEqual(payload);
});

it("prints saved category text without the automatic tenure sentence",()=>{
  const model={orderId:1,orderNumber:'TEST',orderDate:'2026-06-11',status:'DRAFT',statusMark:'draft',organization:{ru:'TEST',kk:'TEST'},title:{ru:'Категория',kk:'Санат'},preamble:null,closing:null,
    documentTypeCode:'QUALIFICATION_CATEGORY',placeOfIssue:{ru:'TEST',kk:'TEST'},items:[{itemId:1,itemNumber:1,itemTypeCode:'QUALIFICATION_CATEGORY',employeeId:1,employeeName:'TEST',effectiveDate:'2026-06-11',
      context:{},body:{ru:'С 11.06.2026 категория будет считаться 7.2 (Р) „высшей“ до 10.06.2031.',kk:'2026 жылғы 11 маусымнан бастап санаты 7.2 (R) „жоғары“ 2031 жылғы 10 маусымға дейін болып есептелсін.'},basis:null}],basis:[],signatory:{position:null,fio:null},acknowledgements:[],executorName:'TEST'} as unknown as PersonnelOrderPrintViewModel;
  const html=buildPersonnelOrderPrintDocumentHtml(model,'kk-ru');
  expect(html).toContain('„высшей“');expect(html).toContain('„жоғары“');
  expect(html).not.toContain('Стаж работы');expect(html).not.toContain('Жұмыс өтілі');
});
