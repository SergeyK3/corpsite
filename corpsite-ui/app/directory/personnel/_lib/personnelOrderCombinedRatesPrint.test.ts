import {readFileSync, writeFileSync} from "node:fs";
import path from "node:path";
import {describe,expect,it} from "vitest";
import {buildPersonnelOrderPrintViewModel} from "./personnelOrderPrintViewModel";
import {buildPersonnelOrderPrintDocumentHtml} from "./personnelOrderPrintDocumentHtml";
import {PERSONNEL_ORDER_PRINT_DOCUMENT_CSS} from "./personnelOrderPrintDocumentCss";

const fixtureDir=process.env.CASE_RESULTS_DIR || process.env.T30_RESULTS_DIR;
describe.skipIf(!fixtureDir)("temporary PostgreSQL transfer + additional rate print",()=>{
 it.each([['0.25','1.25'],['0.5','1.5'],['0.75','1.75']])("preserves both languages, numbering and title for %s / %s",(rate,total)=>{
  const fixture=JSON.parse(readFileSync(path.join(fixtureDir!,`rate-${rate}.json`),'utf8'));
  const model=buildPersonnelOrderPrintViewModel(fixture.detail,{editorial:fixture.editorial});
  expect(model.items).toHaveLength(2);
  const employeeId=fixture.detail.items[0].employee_id;
  expect(employeeId).toBeTruthy();
  expect(model.items.map(item=>item.employeeId)).toEqual([employeeId,employeeId]);
  for(const locale of ['ru','kk'] as const){
   const html=buildPersonnelOrderPrintDocumentHtml(model,locale);
   const doc=new DOMParser().parseFromString(html,'text/html');
   expect(doc.querySelectorAll('[data-testid="personnel-order-print-header"]')).toHaveLength(1);
   expect(doc.querySelectorAll('.personnel-order-print-preamble')).toHaveLength(1);
   const items=Array.from(doc.querySelectorAll('[data-testid^="personnel-order-print-item-"]'));
   expect(items).toHaveLength(2);
   expect(items[0].textContent?.trim()).toMatch(/^1\./);
   expect(items[1].textContent?.trim()).toMatch(/^2\./);
   expect(items[1].textContent).toContain(rate.replace('.',','));
   expect(items[1].textContent).toContain(total.replace('.',','));
   expect(items[1].textContent).not.toContain(rate);
   expect(items[1].textContent).not.toContain(total);
   expect(doc.body.textContent).not.toContain('{{');
   expect(doc.body.textContent).toContain(locale==='ru'?'О переводе и дополнительной нагрузке':'Ауыстыру және қосымша жүктеме туралы');
   expect(items[0].textContent).toContain(locale==='ru'?'Перевести Тестову Анну Ивановну':'Тестова Анна Ивановна;');
   const standalone=`<!doctype html><html lang="${locale}"><head><meta charset="utf-8"><style>${PERSONNEL_ORDER_PRINT_DOCUMENT_CSS}</style></head><body>${html}</body></html>`;
   writeFileSync(path.join(fixtureDir!,`rate-${rate}-${locale}.html`),standalone,'utf8');
  }
 });
});
