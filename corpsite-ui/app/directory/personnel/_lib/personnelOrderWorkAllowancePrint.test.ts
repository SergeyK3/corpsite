import {expect, it} from "vitest";
import {buildPersonnelOrderPrintViewModel} from "./personnelOrderPrintViewModel";
import {buildPersonnelOrderPrintDocumentHtml} from "./personnelOrderPrintDocumentHtml";
import type {PersonnelOrderDetailResponse,PersonnelOrderEditorialState} from "./personnelOrdersApi.client";

it.each(['ru','kk'] as const)('prints allowance and total without editorial fallback inventing a rate (%s)', language=>{
  const detail={order:{order_id:1,order_type_code:'CONCURRENT_DUTY_START',status:'DRAFT'},items:[{item_id:1,item_number:1,item_type_code:'CONCURRENT_DUTY_START',item_status:'ACTIVE',employee_id:7,employee_name:'Тестовый Сотрудник',effective_date:'2026-02-02',payload:{concurrent:{employee_dative_ru:'Тестовому Сотруднику',employee_dative_kk:'Сынақ Қызметкеріне',position_genitive_ru:'врача-реабилитолога',org_unit_genitive_ru:'инсультного центра',position_kk:'реабилитолог дәрігері',org_unit_kk:'инсульт орталығының',total_rate:1.25},replacement:{mode:'WORK_ALLOWANCE',allowance_percent:25,allowance_basis_ru:'должностного оклада',allowance_basis_kk:'лауазымдық айлық ақыдан'}}}],localized_texts:[]} as unknown as PersonnelOrderDetailResponse;
  const before=JSON.stringify(detail);
  const model=buildPersonnelOrderPrintViewModel(detail);
  const html=buildPersonnelOrderPrintDocumentHtml(model,language);
  const doc=new DOMParser().parseFromString(html,'text/html');
  const body=doc.querySelector('[data-testid="personnel-order-print-item-1"]')!.textContent!;
  expect(body).toContain('25');expect(body).toContain('1,25');expect(body).not.toContain('0,25');
  if(language==='kk'){expect(body).toContain('лауазымдық айлық ақыдан 25 %');expect(body).toContain('төленсін.');expect(body).not.toContain('төленсін..');}
  else expect(body).toContain('врача-реабилитолога инсультного центра');
  expect(model.items[0].context.concurrentRate).toBeNull();
  expect(JSON.stringify(detail)).toBe(before);
  const editorial={order_id:1,order_status:'DRAFT',order_blocks:[],items:[{order_item_id:1,blocks:[{locale:language,block_type:'body',generated_text:body,override_text:`Ручная правка ${language} 25% 1,25`}]}]} as unknown as PersonnelOrderEditorialState;
  const saved=buildPersonnelOrderPrintDocumentHtml(buildPersonnelOrderPrintViewModel(detail,{editorial}),language);
  expect(saved).toContain(`Ручная правка ${language} 25% 1,25`);
});
