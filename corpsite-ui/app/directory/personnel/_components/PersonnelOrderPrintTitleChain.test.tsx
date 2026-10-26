import {cleanup,render,screen} from '@testing-library/react';
import {afterEach,expect,it} from 'vitest';
import PersonnelOrderDocumentView from './PersonnelOrderDocumentView';
import {renderPersonnelOrderDocument} from './personnelOrderDocumentTemplates';
import {buildPersonnelOrderPrintViewModel} from '../_lib/personnelOrderPrintViewModel';
import {buildPersonnelOrderPrintDocumentHtml} from '../_lib/personnelOrderPrintDocumentHtml';
import type {PersonnelOrderDetailResponse,PersonnelOrderEditorialState} from '../_lib/personnelOrdersApi.client';

afterEach(cleanup);

const titles=[
  ['HIRE','О приёме на работу'],['TRANSFER','О переводе'],['TERMINATION','Об увольнении'],
  ['CONCURRENT_DUTY_START','О замещении'],['CONCURRENT_DUTY_END','О прекращении совмещения'],
  ['LEAVE.ANNUAL.GRANT','О трудовом отпуске'],['LEAVE.UNPAID.GRANT','Об отпуске без содержания'],
  ['LEAVE.CHILDCARE.GRANT','О неоплачиваемом отпуске по уходу за ребенком'],
  ['LEAVE.ANNUAL.RECALL','Об отзыве из отпуска'],['SUPPLEMENTARY_PAY','О дополнительной оплате'],
  ['RETURN_FROM_CHILDCARE_LEAVE','О выходе на работу из отпуска по уходу за ребёнком'],
] as const;

function isolated(code:string,official:string){
  const internal=code==='CONCURRENT_DUTY_START'
    ?'О совмещении (О замещении на время отпуска как доп ставка)':`${official} (TEST internal picker explanation)`;
  const detail={
    order:{order_id:99001,order_number:'ISOLATED-PRINT-TITLE',order_date:'2026-07-01',order_type_code:code,
      order_class:'SIMPLE',status:'DRAFT',source_mode:'MANUAL',created_by:1,
      source_title:internal,storage_json:{template_snapshot:{title_ru:internal,print_title_ru:official}}},
    print_title_snapshot:{template_version_id:8001,print_title_ru:official,print_title_kk:'TEST saved KK heading',template_title_ru:internal,template_title_kk:'TEST internal KK',legacy:false,requires_update:false,missing_locales:[]},
    items:[{item_id:1,order_id:99001,item_number:1,item_type_code:code,item_status:'ACTIVE',employee_name:'TEST employee',payload:{}}],
    localized_texts:[{locale:'ru',title:internal},{locale:'kk',title:'TEST old localized KK'}],
    attachments:[],prints:[],events:[],
  } as unknown as PersonnelOrderDetailResponse;
  const editorial={order_id:99001,order_status:'DRAFT',editable:true,
    order_blocks:(['ru','kk'] as const).flatMap((locale,index)=>[
      {block_id:index+1,scope:'order',locale,block_type:'title',generated_text:locale==='ru'?internal:'TEST old generated KK',override_text:null,effective_text:locale==='ru'?internal:'TEST old generated KK',revision:1},
      {block_id:index+11,scope:'order',locale,block_type:'preamble',generated_text:'TEST preamble',override_text:null,effective_text:'TEST preamble',revision:1},
    ]),
    items:[{order_item_id:1,item_number:1,item_type_code:code,basis_required:false,
      blocks:(['ru','kk'] as const).map((locale,index)=>({block_id:index+100,scope:'item',order_item_id:1,locale,block_type:'body',generated_text:'TEST saved body',override_text:null,effective_text:'TEST saved body',revision:1}))}],
  } as unknown as PersonnelOrderEditorialState;
  return {detail,editorial,internal};
}

it.each(titles)('uses the frozen paper heading throughout API → preview → print HTML for %s',(code,official)=>{
  const {detail,editorial,internal}=isolated(code,official);
  const before=JSON.stringify({detail,editorial});
  expect(renderPersonnelOrderDocument(detail,'ru',editorial)?.title).toBe(official);
  render(<PersonnelOrderDocumentView detail={detail} language="ru" editorial={editorial}/>);
  expect(screen.getByRole('heading',{level:3,name:official})).toBeInTheDocument();
  expect(screen.queryByRole('heading',{name:internal})).not.toBeInTheDocument();
  const model=buildPersonnelOrderPrintViewModel(detail,{editorial});
  expect(model.title.ru).toBe(official);
  const html=buildPersonnelOrderPrintDocumentHtml(model,'ru');
  const parsed=document.createElement('div');parsed.innerHTML=html;
  expect(parsed.querySelector('.personnel-order-print-title')?.textContent).toBe(official);
  expect(html).not.toContain(internal);
  expect(detail.order.source_title).toBe(internal);
  expect(JSON.stringify({detail,editorial})).toBe(before);
});

it('preserves official parentheses and explicitly saved manual document titles',()=>{
  const official='О приёме (по совместительству)';
  const {detail,editorial}=isolated('HIRE',official);
  expect(renderPersonnelOrderDocument(detail,'ru',editorial)?.title).toBe(official);
  expect(buildPersonnelOrderPrintDocumentHtml(buildPersonnelOrderPrintViewModel(detail,{editorial}),'ru')).toContain(official);
  editorial.order_blocks.find(block=>block.locale==='ru' && block.block_type==='title')!.override_text='TEST official manual (parentheses)';
  expect(renderPersonnelOrderDocument(detail,'ru',editorial)?.title).toBe('TEST official manual (parentheses)');
  expect(buildPersonnelOrderPrintViewModel(detail,{editorial}).title.ru).toBe('TEST official manual (parentheses)');
});

it('does not print a copied internal name even when the old editor stored it as a title override',()=>{
  const {detail,editorial,internal}=isolated('CONCURRENT_DUTY_START','О замещении');
  editorial.order_blocks.find(block=>block.locale==='ru' && block.block_type==='title')!.override_text=internal;
  expect(renderPersonnelOrderDocument(detail,'ru',editorial)?.title).toBe('О замещении');
  expect(buildPersonnelOrderPrintViewModel(detail,{editorial}).title.ru).toBe('О замещении');
  expect(detail.order.source_title).toBe(internal);
  expect(editorial.order_blocks.find(block=>block.locale==='ru' && block.block_type==='title')!.override_text).toBe(internal);
});

it('keeps an old snapshot intact and marks its title as requiring an explicit snapshot update',()=>{
  const {detail,editorial,internal}=isolated('CONCURRENT_DUTY_START','О замещении');
  detail.print_title_snapshot={template_version_id:8001,print_title_ru:null,print_title_kk:null,legacy:true,requires_update:true,missing_locales:['ru','kk']};
  const before=JSON.stringify({detail,editorial});
  expect(renderPersonnelOrderDocument(detail,'ru',editorial)?.title).toBe(internal);
  expect(buildPersonnelOrderPrintViewModel(detail,{editorial}).title.ru).toBe(internal);
  expect(detail.print_title_snapshot.requires_update).toBe(true);
  expect(JSON.stringify({detail,editorial})).toBe(before);
});

it('does not substitute an internal title or translate a missing KK heading',()=>{
  const {detail,editorial}=isolated('CONCURRENT_DUTY_START','О замещении');
  detail.print_title_snapshot={...detail.print_title_snapshot!,print_title_kk:null,requires_update:true,missing_locales:['kk']};
  expect(renderPersonnelOrderDocument(detail,'ru',editorial)?.title).toBe('О замещении');
  expect(renderPersonnelOrderDocument(detail,'kk',editorial)?.title).toBe('[Печатный заголовок KK: требуется согласование]');
  expect(buildPersonnelOrderPrintViewModel(detail,{editorial}).title.kk).toBe('[Печатный заголовок KK: требуется согласование]');
});

it('previews and prints the approved simple concurrent version in both languages after reopening',()=>{
  const internal='О совмещении (простой, как по доп ставке)';
  const {detail,editorial}=isolated('CONCURRENT_DUTY_START','О совмещении');
  detail.order.source_title=internal;
  detail.print_title_snapshot={...detail.print_title_snapshot!,template_title_ru:internal,print_title_kk:'Қоса атқару туралы'};
  editorial.order_blocks.find(block=>block.locale==='ru' && block.block_type==='title')!.generated_text=internal;
  const reopened=JSON.parse(JSON.stringify({detail,editorial})) as {detail:PersonnelOrderDetailResponse;editorial:PersonnelOrderEditorialState};
  const view=render(<PersonnelOrderDocumentView detail={reopened.detail} language="ru" editorial={reopened.editorial}/>);
  expect(screen.getByRole('heading',{level:3,name:'О совмещении'})).toBeInTheDocument();
  expect(screen.queryByText(/требуется согласование/)).not.toBeInTheDocument();
  view.rerender(<PersonnelOrderDocumentView detail={reopened.detail} language="kk" editorial={reopened.editorial}/>);
  expect(screen.getByRole('heading',{level:3,name:'Қоса атқару туралы'})).toBeInTheDocument();
  expect(screen.queryByText(/требуется согласование/)).not.toBeInTheDocument();
  const model=buildPersonnelOrderPrintViewModel(reopened.detail,{editorial:reopened.editorial});
  for(const locale of ['ru','kk'] as const){
    const html=buildPersonnelOrderPrintDocumentHtml(model,locale);
    expect(html).toContain(locale==='ru'?'О совмещении':'Қоса атқару туралы');
    expect(html).not.toContain(internal);
    expect(html).not.toContain('требуется согласование');
  }
  expect(reopened.detail.order.source_title).toBe(internal);
});
