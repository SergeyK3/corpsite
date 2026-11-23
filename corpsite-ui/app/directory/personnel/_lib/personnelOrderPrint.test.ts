import { describe, expect, it } from "vitest";

import {
  PERSONNEL_ORDER_PRINT_LANGUAGE_DEFAULT,
  buildPersonnelOrderPrintHref,
  isPersonnelOrderPrintLanguage,
  isPersonnelOrderPrintRoute,
  parsePersonnelOrderPrintLanguage,
} from "./personnelOrderPrintLanguage";
import { PERSONNEL_ORDER_PRINT_DICTIONARIES, statusMarkLinesForLanguage } from "./personnelOrderPrintLocale";
import {
  formatPersonnelOrderPrintDate,
  formatPersonnelOrderPrintDateLines,
  formatPersonnelOrderPrintStartDate,
  formatPersonnelOrderPrintRate,
  formatPersonnelOrderPrintRateValue,
  parsePersonnelOrderCalendarDate,
} from "./personnelOrderPrintFormat";
import { resolveLocalizedLines, resolveLocalizedText } from "./personnelOrderPrintLocalized";
import { renderPersonnelOrderPrintItemText } from "./personnelOrderPrintItemText";
import {
  buildPersonnelOrderPrintDocumentHtml,
  preambleIncludesOrderVerb,
} from "./personnelOrderPrintDocumentHtml";
import {
  buildPersonnelOrderPrintViewModel,
  type PersonnelOrderPrintViewModel,
} from "./personnelOrderPrintViewModel";
import type { PersonnelOrderDetailResponse } from "./personnelOrdersApi.client";
it.each(['ru','kk'] as const)('prints historical certificate wording and respects deliberately cleared KK basis in %s',language=>{
 const detail=sampleDetail();
 detail.items[0].payload.hire_basis={ru:'личное заявление, трудовой договор',kk:'',kk_intentionally_empty:true};
 detail.items[0].payload.hire_details={education:{code:'',ru:'',kk:''},service_length:{ru:'',kk:''},certificate:{
  specialty:{medical_specialty_id:41,name_ru:'Радиология',name_kk:'Радиология'},name_ru:'Лучевая диагностика',name_kk:'Сәулелік диагностика',issued_on:'2020-01-05'}};
 const html=buildPersonnelOrderPrintDocumentHtml(buildPersonnelOrderPrintViewModel(detail),language);
 expect(html).toContain(language==='ru'?'Сертификат: Лучевая диагностика':'Сертификат: Сәулелік диагностика');
 expect(html).not.toContain('Сертификат: Радиология');
 if(language==='kk')expect(html).not.toContain('личное заявление, трудовой договор');
});

it.each(['ru','kk'] as const)('prints HIRE paired basis and optional certificate in %s without cross-language fallback',language=>{
  const detail=sampleDetail();
  detail.order.source_title_locale='ru';
  detail.items[0].payload.hire_basis={ru:'Ручное основание RU TEST',kk:'Қолмен негіз KK TEST'};
  detail.items[0].payload.hire_details={education:{code:'',ru:'',kk:''},service_length:{ru:'',kk:''},certificate:{
    specialty:{medical_specialty_id:7,name_ru:'Медицина RU TEST',name_kk:'Медицина KK TEST'},issued_on:'2026-02-02'}};
  let html=buildPersonnelOrderPrintDocumentHtml(buildPersonnelOrderPrintViewModel(detail),language);
  expect(html).toContain(language==='ru'?'Ручное основание RU TEST':'Қолмен негіз KK TEST');
  expect(html).not.toContain(language==='kk'?'Ручное основание RU TEST':'Қолмен негіз KK TEST');
  expect(html).toContain(language==='ru'?'Сертификат: Медицина RU TEST':'Сертификат: Медицина KK TEST');
  expect(html).toContain(language==='ru'?'2 февраля 2026 года':'2026 жылғы 2 ақпан');
  detail.items[0].payload.hire_basis.kk='';
  detail.items[0].payload.hire_details.certificate={specialty:null,issued_on:''};
  html=buildPersonnelOrderPrintDocumentHtml(buildPersonnelOrderPrintViewModel(detail),'kk');
  expect(html).not.toContain('Ручное основание RU TEST');
  expect(html).not.toContain('Сертификат:');
  expect(html).not.toContain('берілген күні:');
});

it.each(['ru','kk','kk-ru'] as const)('prints one saved HIRE decimal years value in %s and keeps explicit zero', language => {
  const detail = sampleDetail();
  detail.items[0].payload.hire_details = {education:{code:'',ru:'',kk:''},service_length:{ru:'OLD RU',kk:'OLD KK'},service_length_years:'17.3'};
  let html = buildPersonnelOrderPrintDocumentHtml(buildPersonnelOrderPrintViewModel(detail),language);
  if (language !== 'kk') expect(html).toContain('Трудовой стаж: 17,3 года');
  if (language !== 'ru') expect(html).toContain('Еңбек өтілі: 17,3 жыл');
  expect(html).not.toContain('OLD RU'); expect(html).not.toContain('OLD KK');
  detail.items[0].payload.hire_details = {education:{code:'',ru:'',kk:''},service_length:{ru:'OLD RU',kk:'OLD KK'},service_length_years:'0'};
  html = buildPersonnelOrderPrintDocumentHtml(buildPersonnelOrderPrintViewModel(detail),language);
  if (language !== 'kk') expect(html).toContain('Трудовой стаж: 0 лет');
  if (language !== 'ru') expect(html).toContain('Еңбек өтілі: 0 жыл');
  detail.items[0].payload.hire_details.service_length_years = '';
  html = buildPersonnelOrderPrintDocumentHtml(buildPersonnelOrderPrintViewModel(detail),language);
  for (const text of ['Трудовой стаж:', 'Еңбек өтілі:', 'OLD RU', 'OLD KK']) expect(html).not.toContain(text);
});

it.each(['ru', 'kk', 'kk-ru'] as const)('prints optional HIRE education and tenure only in the selected language %s', language => {
  const detail = sampleDetail();
  detail.items[0].payload.hire_details = {education: {code: 'HIGHER', ru: 'Высшее TEST', kk: 'Жоғары TEST'}, service_length: {ru: '5 лет TEST', kk: '5 жыл TEST'}};
  const html = buildPersonnelOrderPrintDocumentHtml(buildPersonnelOrderPrintViewModel(detail), language);
  if (language !== 'kk') {expect(html).toContain('Образование: Высшее TEST'); expect(html).toContain('Трудовой стаж: 5 лет TEST');}
  if (language !== 'ru') {expect(html).toContain('Білімі: Жоғары TEST'); expect(html).toContain('Еңбек өтілі: 5 жыл TEST');}
  if (language === 'kk') expect(html).not.toContain('5 лет TEST');
  if (language === 'ru') expect(html).not.toContain('5 жыл TEST');
  expect(html).not.toContain('Стаж работы ещё не определён');
  expect(html).not.toContain('Жұмыс өтілі әлі анықталмаған');
  delete detail.items[0].payload.hire_details;
  const empty = buildPersonnelOrderPrintDocumentHtml(buildPersonnelOrderPrintViewModel(detail), language);
  for (const label of ['Образование:', 'Білімі:', 'Трудовой стаж:', 'Еңбек өтілі:', 'Стаж работы ещё не определён', 'Жұмыс өтілі әлі анықталмаған']) expect(empty).not.toContain(label);
});

it.each([
  ['2026-02-02', 'с 02.02.2026', '2026 жылғы 2 ақпаннан бастап'],
  ['2020-01-05', 'с 05.01.2020', '2020 жылғы 5 қаңтардан бастап'],
])('formats HIRE action dates in generated RU/KK print without changing ISO storage: %s', (iso, ru, kk) => {
  const detail = sampleDetail();
  detail.items[0].effective_date = iso;
  const model = buildPersonnelOrderPrintViewModel(detail);
  for (const [locale, expected] of [['ru', ru], ['kk', kk]] as const) {
    const html = buildPersonnelOrderPrintDocumentHtml(model, locale);
    expect(html).toContain(expected);
    expect(html).not.toContain(iso);
  }
  expect(detail.items[0].effective_date).toBe(iso);
});

it('preserves manually written HIRE date wording in RU/KK print', () => {
  const detail = sampleDetail();
  detail.items[0].effective_date = '2026-02-02';
  const manual = {ru: 'SYNTHETIC MANUAL RU с 2026-02-02.', kk: 'SYNTHETIC MANUAL KK 2026-02-02 бастап.'};
  const model = buildPersonnelOrderPrintViewModel(detail, {editorial: {
    order_id: 42, order_status: 'DRAFT', editable: true, order_blocks: [],
    items: [{order_item_id: 1, item_number: 1, item_type_code: 'HIRE', basis_required: true,
      blocks: (['ru', 'kk'] as const).map((locale, index) => ({
        block_id: 10 + index, scope: 'item', order_item_id: 1, locale, block_type: 'body',
        generated_text: 'SYNTHETIC GENERATED', override_text: manual[locale], effective_text: manual[locale],
        revision: 1, editable: true, review_status: 'CURRENT',
      })),
    }],
  }});
  for (const locale of ['ru', 'kk'] as const) expect(buildPersonnelOrderPrintDocumentHtml(model, locale)).toContain(manual[locale]);
});

it.each(['ru','kk','kk-ru'] as const)('prints explicit new personal-data acknowledgement names in %s without old surname',locale=>{
 const detail=sampleDetail({order_type_code:'PERSONAL_DATA_CHANGE'});detail.items[0].item_type_code='PERSONAL_DATA_CHANGE';
 detail.items[0].payload={personal_data:{new_full_name_ru:'НЕЛЬЗЯ РАЗБИРАТЬ',new_full_name_kk:'ЖОЛДЫ ТАЛДАМАУ',new_surname_ru:'Новая Двойная',new_given_name_ru:'Юлия',new_surname_kk:'Жаңа Тегі',new_given_name_kk:'Әлия'}};
 const model=buildPersonnelOrderPrintViewModel(detail);expect(model.acknowledgements[0].personalDataNames).toEqual({ru:'Новая Двойная Ю.',kk:'Ә. Жаңа Тегі'});
 const html=buildPersonnelOrderPrintDocumentHtml(model,locale);const ack=html.split('data-testid="personnel-order-print-acknowledgement"')[1];
 expect(ack).not.toContain('Петрова');
 if(locale!=='kk')expect(ack).toContain('Новая Двойная Ю.');
 if(locale!=='ru')expect(ack).toContain('Ә. Жаңа Тегі');
});
it('leaves the personal-data acknowledgement blank when explicit parts are missing',()=>{
 const detail=sampleDetail({order_type_code:'PERSONAL_DATA_CHANGE'});detail.items[0].item_type_code='PERSONAL_DATA_CHANGE';detail.items[0].payload={personal_data:{new_full_name_ru:'Новая Анна'}};
 const html=buildPersonnelOrderPrintDocumentHtml(buildPersonnelOrderPrintViewModel(detail),'ru');const ack=html.split('data-testid="personnel-order-print-acknowledgement"')[1];expect(ack).not.toContain('Петрова');expect(ack).not.toContain('Новая');
});

it.each(['TRANSFER','CONCURRENT_DUTY_START','SUPPLEMENTARY_PAY'])('preserves both detailed grounds and punctuation in RU and KK print HTML for %s',code=>{
  const detail=sampleDetail({order_type_code:code,legal_basis_article:null,basis_summary:null});
  detail.items[0].item_type_code=code;
  const phrases={ru:'личное заявление от TEST сотрудника; служебная записка заместителя директора по лечебно-профилактической работе',kk:'жеке өтініш; қызметтік жазба TEST қолмен енгізілген мәтін'};
  const model=buildPersonnelOrderPrintViewModel(detail,{editorial:{order_id:42,order_status:'DRAFT',editable:true,order_blocks:[],
    items:[{order_item_id:1,item_number:1,item_type_code:code,basis_required:true,blocks:(['ru','kk'] as const).flatMap((locale,index)=>[
      {block_id:10+index,scope:'item',order_item_id:1,locale,block_type:'body',generated_text:'TEST body',effective_text:'TEST body',revision:1,editable:true,review_status:'CURRENT'},
      {block_id:20+index,scope:'item',order_item_id:1,locale,block_type:'basis',generated_text:`${locale==='ru'?'Основание':'Негіз'}: ${phrases[locale]}.`,effective_text:'',revision:1,editable:true,review_status:'CURRENT'},
    ])}],
  }});
  for(const locale of ['ru','kk'] as const){
    const html=buildPersonnelOrderPrintDocumentHtml(model,locale);
    expect(html).toContain(phrases[locale]);
    expect(html.split(phrases[locale])).toHaveLength(2);
    expect(html).not.toContain('Основание: Основание:');
    expect(html).not.toContain('Негіз: Негіз:');
    expect(html).not.toContain('работе..');
    expect(html).not.toContain('мәтін..');
  }
});

it('uses the selected position when clarification is empty and preserves the other language when only RU is clarified',()=>{
  const detail=sampleDetail();
  detail.items[0].payload={position_id:20,assignment:{position:{ru:'Штатная должность TEST',kk:'TEST штаттық лауазым'},rate:1},
    document_position:{name:'Выбранная должность TEST',name_kk:'TEST таңдалған лауазым'},
    document_forms_ru:{position_document_nominative_ru:'Выбранная должность TEST'},
    document_forms_kk:{position_document_possessive_kk:'TEST таңдалған лауазымы'}};
  let model=buildPersonnelOrderPrintViewModel(detail);
  expect(model.items[0].context.positionName).toEqual({ru:'Выбранная должность TEST',kk:'TEST таңдалған лауазым'});
  detail.items[0].payload.position_text_override={ru:'Ручная должность TEST',kk:''};
  const reopened=JSON.parse(JSON.stringify(detail)) as PersonnelOrderDetailResponse;
  model=buildPersonnelOrderPrintViewModel(reopened);
  expect(model.items[0].context.positionName).toEqual({ru:'Ручная должность TEST',kk:'TEST таңдалған лауазым'});
  expect(buildPersonnelOrderPrintDocumentHtml(model,'ru').toLowerCase()).toContain('ручная должность test');
  expect(buildPersonnelOrderPrintDocumentHtml(model,'kk')).toContain('TEST таңдалған лауазымы');
  reopened.items[0].payload.position_text_override={ru:'',kk:''};
  reopened.items[0].payload.assignment={position:{ru:'Штатная должность TEST',kk:'TEST штаттық лауазым'},position_text_override:{ru:'Legacy override',kk:'Legacy KK'}};
  expect(buildPersonnelOrderPrintViewModel(reopened).items[0].context.positionName).toEqual({ru:'Выбранная должность TEST',kk:'TEST таңдалған лауазым'});
  expect(reopened.items[0].payload.position_id).toBe(20);
});

it.each([
  ['HIRE','О приёме на работу','Жұмысқа қабылдау туралы'],
  ['TRANSFER','О переводе','Ауыстыру туралы'],
  ['CONCURRENT_DUTY_START','О совмещении','Қоса атқару туралы'],
  ['LEAVE.ANNUAL.GRANT','О трудовом отпуске','Еңбек демалысы туралы'],
])('prints the saved official heading for %s without substituting a detailed internal name', (code,ru,kk)=>{
  const detail=sampleDetail({order_type_code:code});
  detail.localized_texts.forEach(row=>{row.title='TEST detailed internal name (HR explanation)';});
  const model=buildPersonnelOrderPrintViewModel(detail,{editorial:{
    order_id:42,order_status:'DRAFT',editable:true,items:[],
    order_blocks:([['ru',ru],['kk',kk]] as const).map(([locale,title],index)=>({
      block_id:900+index,scope:'order',locale,block_type:'title',generated_text:`${title} (TEST official parentheses)`,
      override_text:null,effective_text:`${title} (TEST official parentheses)`,revision:1,editable:true,review_status:'CURRENT',
    })),
  }});
  for(const locale of ['ru','kk'] as const){
    const html=buildPersonnelOrderPrintDocumentHtml(model,locale);
    expect(html).toContain(`${locale==='ru'?ru:kk} (TEST official parentheses)`);
    expect(html).not.toContain('TEST detailed internal name');
  }
});

it.each(["ru", "kk"] as const)("prints saved supplementary-pay points with their own basis exactly once (%s)", language => {
  const detail = sampleDetail({order_type_code: "SUPPLEMENTARY_PAY", legal_basis_article: null, basis_summary: null});
  detail.items = [25, 50].map((percent, index) => ({...detail.items[0], item_id: index + 1, item_number: index + 1, item_type_code: "SUPPLEMENTARY_PAY", employee_id: index + 7, payload: {allowance: {percent}}}));
  const model = buildPersonnelOrderPrintViewModel(detail, {editorial: {
    order_id: 42, order_status: "DRAFT", editable: true,
    order_blocks: (["ru", "kk"] as const).flatMap(locale => [
      {block_id: 100, scope: "order", locale, block_type: "title", generated_text: locale === "ru" ? "Сохранённый заголовок" : "Сақталған атау", effective_text: "", revision: 1, editable: true, review_status: "CURRENT"},
      {block_id: 101, scope: "order", locale, block_type: "preamble", generated_text: locale === "ru" ? "Сохранённая преамбула" : "Сақталған кіріспе", effective_text: "", revision: 1, editable: true, review_status: "CURRENT"},
    ]),
    items: detail.items.map((item, index) => ({order_item_id: item.item_id, item_number: item.item_number, item_type_code: item.item_type_code, basis_required: true,
      blocks: (["ru", "kk"] as const).flatMap(locale => [
        {block_id: 200 + index, scope: "item", order_item_id: item.item_id, locale, block_type: "body", generated_text: `Saved ${locale} employee ${index + 1}: ${index ? 50 : 25}%`, effective_text: "", revision: 1, editable: true, review_status: "CURRENT"},
        {block_id: 300 + index, scope: "item", order_item_id: item.item_id, locale, block_type: "basis", generated_text: locale === "ru" ? `Основание: Заявление ${index + 1}.` : `Негіз: Өтініш ${index + 1}.`, effective_text: "", revision: 1, editable: true, review_status: "CURRENT"},
      ]),
    })),
  }});
  const html = buildPersonnelOrderPrintDocumentHtml(model, language);
  expect(html).toContain(language === "ru" ? "Сохранённый заголовок" : "Сақталған атау");
  expect(html).toContain(language === "ru" ? "Сохранённая преамбула" : "Сақталған кіріспе");
  expect(html).toContain(`Saved ${language} employee 1: 25%`);
  expect(html).toContain(`Saved ${language} employee 2: 50%`);
  expect(html.match(language === "ru" ? /Основание:/g : /Негіз:/g)).toHaveLength(2);
  expect(html).not.toContain("Основание: Основание:");
  expect(html).not.toContain("DOCX");
  expect(html).not.toContain("Стаж работы");
  expect(html).not.toContain("Жұмыс өтілі");
  expect(model.basis).toEqual([]);
});

function sampleDetail(overrides?: Partial<PersonnelOrderDetailResponse["order"]>): PersonnelOrderDetailResponse {
  return {
    order: {
      order_id: 42,
      order_number: "12-К",
      order_date: "2026-07-10",
      order_type_code: "HIRE",
      order_class: "SIMPLE",
      status: "DRAFT",
      source_mode: "PAPER",
      legal_basis_article: "ст. 33 ТК РК",
      basis_summary: "Заявление работника",
      signed_by_name: "Иванов И.И.",
      signed_by_position: "Директор",
      created_by: 1,
      ...overrides,
    },
    items: [
      {
        item_id: 1,
        order_id: 42,
        item_number: 1,
        item_type_code: "HIRE",
        item_status: "ACTIVE",
        employee_id: 7,
        employee_name: "Петрова Анна",
        effective_date: "2026-07-15",
        payload: {
          org_unit_id: 10,
          position_id: 20,
          employment_rate: 1,
        },
      },
    ],
    localized_texts: [
      {
        localized_text_id: 1,
        order_id: 42,
        locale: "kk",
        title: "Жұмысқа қабылдау туралы",
        preamble: null,
        body_text: null,
        render_version: 1,
        is_authoritative: true,
      },
      {
        localized_text_id: 2,
        order_id: 42,
        locale: "ru",
        title: "О приёме на работу",
        preamble: null,
        body_text: null,
        render_version: 1,
        is_authoritative: false,
      },
    ],
    attachments: [],
    prints: [],
    events: [],
  };
}

describe("personnelOrderPrintLanguage", () => {
  it("accepts kk, ru, kk-ru", () => {
    expect(isPersonnelOrderPrintLanguage("kk")).toBe(true);
    expect(isPersonnelOrderPrintLanguage("ru")).toBe(true);
    expect(isPersonnelOrderPrintLanguage("kk-ru")).toBe(true);
    expect(isPersonnelOrderPrintLanguage("en")).toBe(false);
  });

  it("parses missing and unknown language values", () => {
    expect(parsePersonnelOrderPrintLanguage(null)).toBe(PERSONNEL_ORDER_PRINT_LANGUAGE_DEFAULT);
    expect(parsePersonnelOrderPrintLanguage(undefined)).toBe("ru");
    expect(parsePersonnelOrderPrintLanguage("kk")).toBe("kk");
    expect(parsePersonnelOrderPrintLanguage("unknown")).toBeNull();
    expect(parsePersonnelOrderPrintLanguage("unknown", { fallbackToDefault: true })).toBe("ru");
  });

  it("builds print href and detects print route", () => {
    expect(buildPersonnelOrderPrintHref(42, "kk-ru")).toBe(
      "/directory/personnel/orders/42/print?language=kk-ru",
    );
    expect(isPersonnelOrderPrintRoute("/directory/personnel/orders/42/print")).toBe(true);
    expect(isPersonnelOrderPrintRoute("/directory/personnel/orders")).toBe(false);
  });
});

describe("personnelOrderPrint localization", () => {
  it("keeps service headings language-specific", () => {
    expect(PERSONNEL_ORDER_PRINT_DICTIONARIES.ru.documentType).toBe("ПРИКАЗ");
    expect(PERSONNEL_ORDER_PRINT_DICTIONARIES.kk.documentType).toBe("БҰЙРЫҚ");
    expect(PERSONNEL_ORDER_PRINT_DICTIONARIES.ru.orderVerb).toContain("ПРИКАЗЫВАЮ");
    expect(PERSONNEL_ORDER_PRINT_DICTIONARIES.kk.orderVerb).toContain("БҰЙЫРАМЫН");
    expect(PERSONNEL_ORDER_PRINT_DICTIONARIES.ru.draft).toBe("ПРОЕКТ");
    expect(PERSONNEL_ORDER_PRINT_DICTIONARIES.kk.draft).toBe("ЖОБА");
    expect(PERSONNEL_ORDER_PRINT_DICTIONARIES.ru.readyForSignature).toBe("НА ПОДПИСЬ");
    expect(PERSONNEL_ORDER_PRINT_DICTIONARIES.kk.readyForSignature).toBe("ҚОЛ ҚОЮҒА");
  });

  it("maps print watermarks to human-facing labels", () => {
    expect(statusMarkLinesForLanguage("draft", "ru")).toEqual(["ПРОЕКТ"]);
    expect(statusMarkLinesForLanguage("draft", "kk")).toEqual(["ЖОБА"]);
    expect(statusMarkLinesForLanguage("draft", "kk-ru")).toEqual(["ЖОБА / ПРОЕКТ"]);
    expect(statusMarkLinesForLanguage("unsigned", "ru")).toEqual(["НА ПОДПИСЬ"]);
    expect(statusMarkLinesForLanguage("unsigned", "kk")).toEqual(["ҚОЛ ҚОЮҒА"]);
    expect(statusMarkLinesForLanguage("unsigned", "kk-ru")).toEqual(["ҚОЛ ҚОЮҒА / НА ПОДПИСЬ"]);
    expect(statusMarkLinesForLanguage("cancelled", "ru")).toEqual(["АННУЛИРОВАН"]);
    expect(statusMarkLinesForLanguage("cancelled", "kk")).toEqual(["КҮШІ ЖОЙЫЛҒАН"]);
  });

  it("falls back without undefined/null technical values", () => {
    expect(resolveLocalizedText({ kk: null, ru: undefined }, "kk", "fallback")).toBe("fallback");
    expect(resolveLocalizedLines({ kk: "A", ru: "A" }, "kk-ru")).toEqual(["A"]);
    expect(resolveLocalizedLines({ kk: "A", ru: "B" }, "kk-ru")).toEqual(["A", "B"]);
    expect(resolveLocalizedText({}, "ru")).toBe("—");
  });
});

describe("personnelOrderPrint formatters", () => {
  it("formats calendar dates without timezone shift", () => {
    expect(parsePersonnelOrderCalendarDate("2026-07-10")).toEqual({
      year: 2026,
      month: 7,
      day: 10,
    });
    expect(formatPersonnelOrderPrintDate("2026-07-10", "ru")).toBe("10 июля 2026 года");
    expect(formatPersonnelOrderPrintDate("2026-07-10", "kk")).toBe("2026 жылғы 10 шілде");
    expect(formatPersonnelOrderPrintDateLines("2026-07-10", "kk-ru")).toEqual([
      "2026 жылғы 10 шілде",
      "10 июля 2026 года",
    ]);
  });

  it("declines Kazakh start dates for every month", () => {
    const monthSuffixes = [
      "\u049b\u0430\u04a3\u0442\u0430\u0440\u0434\u0430\u043d", "\u0430\u049b\u043f\u0430\u043d\u043d\u0430\u043d", "\u043d\u0430\u0443\u0440\u044b\u0437\u0434\u0430\u043d", "\u0441\u04d9\u0443\u0456\u0440\u0434\u0435\u043d", "\u043c\u0430\u043c\u044b\u0440\u0434\u0430\u043d", "\u043c\u0430\u0443\u0441\u044b\u043c\u043d\u0430\u043d",
      "\u0448\u0456\u043b\u0434\u0435\u0434\u0435\u043d", "\u0442\u0430\u043c\u044b\u0437\u0434\u0430\u043d", "\u049b\u044b\u0440\u043a\u04af\u0439\u0435\u043a\u0442\u0435\u043d", "\u049b\u0430\u0437\u0430\u043d\u043d\u0430\u043d", "\u049b\u0430\u0440\u0430\u0448\u0430\u0434\u0430\u043d", "\u0436\u0435\u043b\u0442\u043e\u049b\u0441\u0430\u043d\u043d\u0430\u043d",
    ];
    monthSuffixes.forEach((month, index) => {
      const value = `2026-${String(index + 1).padStart(2, "0")}-05`;
      expect(formatPersonnelOrderPrintStartDate(value, "kk")).toBe(`2026 \u0436\u044b\u043b\u0493\u044b 5 ${month}`);
    });
  });

  it("formats rates by language", () => {
    expect(formatPersonnelOrderPrintRateValue(1)).toBe("1,0");
    expect(formatPersonnelOrderPrintRate(1, "ru")).toContain("ставки");
    expect(formatPersonnelOrderPrintRate(1, "kk")).toContain("мөлшерлеме");
  });
});

describe("buildPersonnelOrderPrintViewModel", () => {
  it("builds normalized print model with draft watermark and acknowledgements", () => {
    const model = buildPersonnelOrderPrintViewModel(sampleDetail(), {
      organizationName: "ММЦ г. Астана",
      orgUnitNames: { 10: "Хирургия" },
      positionNames: { 20: "Врач" },
    });

    expect(model.orderId).toBe(42);
    expect(model.orderNumber).toBe("12-К");
    expect(model.orderDate).toBe("2026-07-10");
    expect(model.statusMark).toBe("draft");
    expect(model.title.kk).toBe("Жұмысқа қабылдау туралы");
    expect(model.title.ru).toBe("О приёме на работу");
    expect(model.items).toHaveLength(1);
    expect(model.items[0]?.context.orgUnitName?.ru).toBe("Хирургия");
    expect(model.basis.length).toBeGreaterThan(0);
    expect(model.signatory?.fio).toBe("Иванов И.И.");
    expect(model.signatory?.position?.ru).toBe("Директор");
    expect(model.acknowledgements).toEqual([
      { employeeId: 7, employeeName: "Петрова Анна", acknowledgedOn: null },
    ]);
  });

  it("marks draft/unsigned/registered/voided correctly", () => {
    expect(buildPersonnelOrderPrintViewModel(sampleDetail({ status: "DRAFT" })).statusMark).toBe(
      "draft",
    );
    expect(
      buildPersonnelOrderPrintViewModel(sampleDetail({ status: "READY_FOR_SIGNATURE" })).statusMark,
    ).toBe("unsigned");
    expect(buildPersonnelOrderPrintViewModel(sampleDetail({ status: "SIGNED" })).statusMark).toBe(
      "none",
    );
    expect(
      buildPersonnelOrderPrintViewModel(sampleDetail({ status: "REGISTERED" })).statusMark,
    ).toBe("none");
    expect(buildPersonnelOrderPrintViewModel(sampleDetail({ status: "VOIDED" })).statusMark).toBe(
      "cancelled",
    );
  });

  it("uses document title for composite instead of technical type label", () => {
    const model = buildPersonnelOrderPrintViewModel(
      {
        ...sampleDetail({ order_type_code: "COMPOSITE", legal_basis_article: null, basis_summary: null }),
        localized_texts: [],
      },
    );
    expect(model.title.ru).toBe("О кадровых изменениях");
    expect(model.title.kk).toBe("Кадрлық өзгерістер туралы");
    expect(model.basis).toEqual([]);
  });

  it("uses the approved return-from-childcare-leave preamble when legacy editorial data is absent", () => {
    const detail = {
      ...sampleDetail({ order_type_code: "RETURN_FROM_CHILDCARE_LEAVE", legal_basis_article: null, basis_summary: null }),
      items: [{
        ...sampleDetail().items[0],
        item_type_code: "RETURN_FROM_CHILDCARE_LEAVE",
        effective_date: "2026-08-05",
        payload: {
          presentation_context: {
            position_name: { ru: "руководитель отдела кадров", kk: "кадрлар бөлімінің басшысы" },
            org_unit_name: { ru: "отдел кадров", kk: "кадрлар бөлімі" },
          },
        },
      }],
      localized_texts: [],
    };
    const model = buildPersonnelOrderPrintViewModel(detail, {});
    expect(model.title.ru).toBe("О выходе на работу из отпуска по уходу за ребёнком");
    expect(model.title.kk).toBe("Бала күтіміне байланысты демалыстан жұмысқа шығу туралы");
    expect(resolveLocalizedLines(model.preamble || {}, "ru")).toEqual([
      "В соответствии с Трудовым кодексом Республики Казахстан",
    ]);
    expect(resolveLocalizedLines(model.preamble || {}, "kk")).toEqual([
      "Қазақстан Республикасының Еңбек кодексіне сәйкес",
    ]);
    const html = buildPersonnelOrderPrintDocumentHtml(model, "ru");
    expect(html.match(/personnel-order-print-order-verb/g) ?? []).toHaveLength(1);
    expect(html).toContain("ПРИКАЗЫВАЮ:");
    expect(html).toContain("Разрешить сотруднику");
    expect(html).not.toContain("Стаж работы ещё не определён.");
    expect(html).not.toContain("RETURN_FROM_CHILDCARE_LEAVE");
  });

  it("resolves signatory position from directory map when order field empty", () => {
    const model = buildPersonnelOrderPrintViewModel(
      sampleDetail({ signed_by_position: null }),
      { signatoryPosition: "Директор" },
    );
    expect(model.signatory.position?.ru).toBe("Директор");
  });

  it("localizes the DIRECTOR system role from a directory fallback in both print languages", () => {
    const model = buildPersonnelOrderPrintViewModel(
      sampleDetail({ signed_by_position: null }),
      { signatoryPosition: "DIRECTOR" },
    );
    expect(model.signatory.position).toEqual({ kk: "Директоры", ru: "Директор" });
  });

  it("prefers editorial effective title/body/basis over legacy and templates", () => {
    const model = buildPersonnelOrderPrintViewModel(sampleDetail(), {
      orgUnitNames: { 10: "Хирургия" },
      positionNames: { 20: "Врач" },
      editorial: {
        order_id: 42,
        order_status: "DRAFT",
        editable: true,
        order_blocks: [
          {
            block_id: 1,
            scope: "order",
            locale: "kk",
            block_type: "title",
            effective_text: "Редакциялық тақырып",
            review_status: "CURRENT",
            editable: true,
            revision: 1,
          },
          {
            block_id: 2,
            scope: "order",
            locale: "ru",
            block_type: "title",
            effective_text: "Редакционный заголовок",
            review_status: "CURRENT",
            editable: true,
            revision: 1,
          },
          {
            block_id: 3,
            scope: "order",
            locale: "ru",
            block_type: "preamble",
            effective_text: "Редакционная преамбула",
            review_status: "CURRENT",
            editable: true,
            revision: 1,
          },
        ],
        items: [
          {
            order_item_id: 1,
            item_number: 1,
            item_type_code: "HIRE",
            basis_required: true,
            blocks: [
              {
                block_id: 10,
                scope: "item",
                order_item_id: 1,
                locale: "ru",
                block_type: "body",
                effective_text: "OVERRIDE BODY RU",
                review_status: "CURRENT",
                editable: true,
                revision: 1,
              },
              {
                block_id: 11,
                scope: "item",
                order_item_id: 1,
                locale: "kk",
                block_type: "body",
                effective_text: "OVERRIDE BODY KK",
                review_status: "CURRENT",
                editable: true,
                revision: 1,
              },
              {
                block_id: 12,
                scope: "item",
                order_item_id: 1,
                locale: "ru",
                block_type: "basis",
                effective_text: "Основание: личное заявление.",
                review_status: "CURRENT",
                editable: true,
                revision: 1,
                basis_required: true,
              },
            ],
          },
        ],
      },
    });

    expect(model.title.ru).toBe("Редакционный заголовок");
    expect(model.title.kk).toBe("Редакциялық тақырып");
    expect(model.preamble?.ru).toBe("Редакционная преамбула");
    expect(model.items[0]?.body?.ru).toBe("OVERRIDE BODY RU");
    expect(model.items[0]?.body?.kk).toBe("OVERRIDE BODY KK");
    expect(model.items[0]?.basis?.ru).toContain("личное заявление");
    expect(model.basis.some((b) => b.ru?.includes("личное заявление"))).toBe(false);
    expect(buildPersonnelOrderPrintDocumentHtml(model,'ru')).toContain('личное заявление');
  });

  it("falls back to legacy localized title when editorial absent", () => {
    const model = buildPersonnelOrderPrintViewModel(sampleDetail(), {});
    expect(model.title.ru).toBe("О приёме на работу");
    expect(model.items[0]?.body).toBeNull();
    expect(model.closing).toBeNull();
  });

  it("maps editorial closing effective text into the view model", () => {
    const model = buildPersonnelOrderPrintViewModel(sampleDetail(), {
      editorial: {
        order_id: 42,
        order_status: "DRAFT",
        editable: true,
        order_blocks: [
          {
            block_id: 50,
            scope: "order",
            locale: "ru",
            block_type: "closing",
            effective_text: "Ознакомить сотрудника с приказом.",
            review_status: "CURRENT",
            editable: true,
            revision: 1,
          },
          {
            block_id: 51,
            scope: "order",
            locale: "kk",
            block_type: "closing",
            effective_text: "Қызметкерді бұйрықпен таныстыру.",
            review_status: "CURRENT",
            editable: true,
            revision: 1,
          },
        ],
        items: [],
      },
    });
    expect(model.closing?.ru).toContain("Ознакомить сотрудника");
    expect(model.closing?.kk).toContain("бұйрықпен таныстыру");
  });

  it("renders closing in shared HTML and omits empty closing", () => {
    const withClosing = buildPersonnelOrderPrintViewModel(sampleDetail(), {
      editorial: {
        order_id: 42,
        order_status: "DRAFT",
        editable: true,
        order_blocks: [
          {
            block_id: 50,
            scope: "order",
            locale: "ru",
            block_type: "closing",
            effective_text: "Ознакомить сотрудника с приказом.",
            review_status: "CURRENT",
            editable: true,
            revision: 1,
          },
        ],
        items: [],
      },
    });
    const html = buildPersonnelOrderPrintDocumentHtml(withClosing, "ru");
    expect(html).toContain('data-testid="personnel-order-print-closing"');
    expect(html).toContain("Ознакомить сотрудника с приказом.");
    expect(html).toContain('data-testid="personnel-order-print-tail-date"');
    expect(html).toContain("10 июля 2026 года");
    expect(html).toContain('data-testid="personnel-order-print-signature"');
    expect(html.indexOf("personnel-order-print-closing")).toBeLessThan(
      html.indexOf("personnel-order-print-tail-date"),
    );
    expect(html.indexOf("personnel-order-print-tail-date")).toBeLessThan(
      html.indexOf("personnel-order-print-signature"),
    );

    const withoutClosing = buildPersonnelOrderPrintViewModel(sampleDetail(), {});
    const htmlEmpty = buildPersonnelOrderPrintDocumentHtml(withoutClosing, "ru");
    expect(htmlEmpty).not.toContain('data-testid="personnel-order-print-closing"');
  });

  it("omits tail date when order_date is empty but keeps signature block", () => {
    const model = buildPersonnelOrderPrintViewModel(sampleDetail({ order_date: null }), {
      editorial: {
        order_id: 42,
        order_status: "DRAFT",
        editable: true,
        order_blocks: [
          {
            block_id: 50,
            scope: "order",
            locale: "ru",
            block_type: "closing",
            effective_text: "Ознакомить сотрудника с приказом.",
            review_status: "CURRENT",
            editable: true,
            revision: 1,
          },
        ],
        items: [],
      },
    });
    const html = buildPersonnelOrderPrintDocumentHtml(model, "ru");
    expect(html).not.toContain('data-testid="personnel-order-print-tail-date"');
    expect(html).toContain('data-testid="personnel-order-print-signature"');
  });

  it("renders tail date once in bilingual HTML", () => {
    const model = buildPersonnelOrderPrintViewModel(sampleDetail(), {
      editorial: {
        order_id: 42,
        order_status: "DRAFT",
        editable: true,
        order_blocks: [
          {
            block_id: 50,
            scope: "order",
            locale: "ru",
            block_type: "closing",
            effective_text: "Ознакомить сотрудника с приказом.",
            review_status: "CURRENT",
            editable: true,
            revision: 1,
          },
        ],
        items: [],
      },
    });
    const html = buildPersonnelOrderPrintDocumentHtml(model, "kk-ru");
    expect(html.match(/data-testid="personnel-order-print-tail-date"/g)?.length).toBe(1);
    expect(html).toContain("2026 жылғы 10 шілде");
    expect(html).toContain("10 июля 2026 года");
  });

  it("keeps one standalone directive when a legacy editorial preamble embeds it", () => {
    const preamble = {
      ru: "В соответствии с Трудовым кодексом Республики Казахстан ПРИКАЗЫВАЮ:",
      kk: null,
    };
    expect(preambleIncludesOrderVerb(preamble, "ru")).toBe(true);

    const custom = { ru: "Редакционная преамбула без глагола.", kk: null };
    expect(preambleIncludesOrderVerb(custom, "ru")).toBe(false);

    const model = buildPersonnelOrderPrintViewModel(sampleDetail(), {
      editorial: {
        order_id: 42,
        order_status: "DRAFT",
        editable: true,
        order_blocks: [
          {
            block_id: 2,
            scope: "order",
            locale: "ru",
            block_type: "preamble",
            effective_text: preamble.ru,
            review_status: "CURRENT",
            editable: true,
            revision: 1,
          },
        ],
        items: [],
      },
    });
    const html = buildPersonnelOrderPrintDocumentHtml(model, "ru");
    const verbMatches = html.match(/personnel-order-print-order-verb/g) ?? [];
    expect(verbMatches).toHaveLength(1);
    expect(html).toContain("ПРИКАЗЫВАЮ:");
  });

  it("preserves item numbering for many active items", () => {
    const manyItems = Array.from({ length: 12 }, (_, index) => ({
      item_id: index + 1,
      order_id: 42,
      item_number: index + 1,
      item_type_code: "HIRE",
      item_status: "ACTIVE",
      employee_id: 100 + index,
      employee_name: `Сотрудник ${index + 1}`,
      effective_date: "2026-07-15",
      payload: {},
    }));
    const model = buildPersonnelOrderPrintViewModel(
      { ...sampleDetail(), items: manyItems },
      {},
    );
    expect(model.items).toHaveLength(12);
    expect(model.items.map((item) => item.itemNumber)).toEqual([
      1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12,
    ]);
    const html = buildPersonnelOrderPrintDocumentHtml(model, "ru");
    expect(html).toContain('12.');
    expect(html).toContain("Сотрудник 12");
  });
});

describe("personnelOrderPrint item text", () => {
  it("renders hire text for ru/kk/kk-ru", () => {
    const model: PersonnelOrderPrintViewModel = buildPersonnelOrderPrintViewModel(sampleDetail(), {
      orgUnitNames: { 10: "Хирургия" },
      positionNames: { 20: "Врач" },
    });
    const ctx = model.items[0]!.context;
    expect(renderPersonnelOrderPrintItemText(ctx, "ru")[0]).toContain("Принять на работу");
    expect(renderPersonnelOrderPrintItemText(ctx, "ru")[0]).toContain('в подразделение «Хирургия» на должность Врач со ставкой');
    expect(renderPersonnelOrderPrintItemText(ctx, "kk")[0]).toContain("жұмысқа қабылдансын");
    expect(renderPersonnelOrderPrintItemText(ctx, "kk-ru")).toHaveLength(2);
  });

  it('keeps HIRE position spelling and internal quotes while quoting only the department',()=>{
    const ctx=buildPersonnelOrderPrintViewModel(sampleDetail(),{}).items[0]!.context;
    const actual={...ctx,payload:{},positionName:{ru:'Врач «УЗИ»',kk:'«УДЗ» Дәрігер'},orgUnitName:{ru:'Отделение «А»',kk:'«А» бөлімше'}};
    const ru=renderPersonnelOrderPrintItemText(actual,'ru')[0],kk=renderPersonnelOrderPrintItemText(actual,'kk')[0];
    expect(ru).toContain('«Отделение «А»» на должность Врач «УЗИ» со ставкой');
    expect(kk).toContain('««А» бөлімше» бөлімшесіне «УДЗ» Дәрігер лауазымына');
  });

  it("renders the Russian concurrent-duty wording with a normalized assignment", () => {
    const text = renderPersonnelOrderPrintItemText(
      {
        itemNumber: 2,
        itemTypeCode: "CONCURRENT_DUTY_START",
        employeeName: "Иванова Алия Сериковна",
        effectiveDate: "2026-07-10",
        orgUnitName: { ru: "Приемное", kk: null },
        positionName: { ru: "Санитар", kk: null },
        toOrgUnitName: null,
        toPositionName: null,
        rate: null,
        toRate: null,
        concurrentRate: 0.5,
        remainingRate: null,
        totalRate: null,
        terminationReason: null,
        payload: {},
      },
      "ru",
    )[0];
    expect(text).toContain("Разрешить сотруднику Иванова Алия Сериковна");
    expect(text).toContain("санитар (приемное отделение)");
    expect(text).toContain("с оплатой 0,5 ставки");
  });

  it("does not print a leave-days placeholder when the source does not confirm days", () => {
    const text = renderPersonnelOrderPrintItemText(
      {
        itemNumber: 1, itemTypeCode: "TERMINATION", employeeName: "Сотрудник", effectiveDate: "2026-02-01",
        orgUnitName: null, positionName: null, toOrgUnitName: null, toPositionName: null,
        rate: null, toRate: null, concurrentRate: null, remainingRate: null, totalRate: null,
        terminationReason: null, payload: {},
      },
      "ru",
    )[0];
    expect(text).not.toContain("Бухгалтерии произвести расчёт");
    expect(text).not.toContain("календарных дней");
    expect(text).not.toContain("— календарных");
  });
});

it("omits saved automatic closing in both languages from the shared print model", () => {
 const model=buildPersonnelOrderPrintViewModel(sampleDetail(),{editorial:{order_id:42,order_status:"DRAFT",editable:true,order_blocks:[{block_id:50,scope:"order",locale:"ru",block_type:"closing",effective_text:"Контроль за исполнением приказа оставляю за собой.",review_status:"CURRENT",editable:true,revision:1},{block_id:51,scope:"order",locale:"kk",block_type:"closing",effective_text:"Бұйрықты орындалу бақылауын өзімде қалдырамын.",review_status:"CURRENT",editable:true,revision:1}],items:[]}});
 expect(model.closing).toBeNull();
 expect(buildPersonnelOrderPrintDocumentHtml(model,"ru")).not.toContain("Контроль за исполнением");
 expect(buildPersonnelOrderPrintDocumentHtml(model,"kk")).not.toContain("бақылауын өзімде");
});


it.each(["Б бөлімі", null])("prints the saved document department instead of employee/assignment fallbacks (KK=%s)", kk => {
  const detail=sampleDetail();
  detail.items[0].payload={...detail.items[0].payload,
    document_org_unit:{unit_id:91,name:"Другой отдел",name_kk:kk,document_genitive_kk:kk?"Б бөлімінің":null},
    presentation_context:{org_unit_name:"Старое подразделение"},
    assignment:{unit:"Старое назначение"},
  };
  const model=buildPersonnelOrderPrintViewModel(detail,{orgUnitNames:{10:"Подразделение карточки"},positionNames:{20:"Врач"}});
  expect(model.items[0].context.orgUnitName?.ru).toBe("Другой отдел");
  expect(model.items[0].context.orgUnitName?.kk).toBe(kk || "—");
  const ru=buildPersonnelOrderPrintDocumentHtml(model,"ru");
  const kz=buildPersonnelOrderPrintDocumentHtml(model,"kk");
  expect(ru.toLowerCase()).toContain("другой отдел");
  expect(ru).not.toContain("Старое подразделение");
  expect(kz).not.toContain("Подразделение карточки");
  if(kk)expect(kz).toContain(kk);
});
