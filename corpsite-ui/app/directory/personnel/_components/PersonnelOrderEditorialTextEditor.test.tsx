import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import * as React from 'react';
import { afterEach, describe, expect, it, vi } from "vitest";

import PersonnelOrderEditorialTextEditor from "./PersonnelOrderEditorialTextEditor";
import type { PersonnelOrderDetailResponse, PersonnelOrderEditorialState, PersonnelOrderItem } from "../_lib/personnelOrdersApi.client";

vi.mock("../_lib/personnelOrdersApi.client", async () => {
  const actual = await vi.importActual<typeof import("../_lib/personnelOrdersApi.client")>(
    "../_lib/personnelOrdersApi.client",
  );
  return {
    ...actual,
    getPersonnelOrder: vi.fn(),
    getPersonnelOrderEditorial: vi.fn(),
    generatePersonnelOrderEditorial: vi.fn(),
    patchPersonnelOrderEditorialBlock: vi.fn(),
    resetPersonnelOrderEditorialBlock: vi.fn(),
    updatePersonnelOrderItem: vi.fn(),
  };
});

import {
  PERSONNEL_ORDER_CREATE_TYPE_OPTIONS,
  generatePersonnelOrderEditorial,
  getPersonnelOrderEditorial,
  getPersonnelOrder,
  patchPersonnelOrderEditorialBlock,
  resetPersonnelOrderEditorialBlock,
  updatePersonnelOrderItem,
} from "../_lib/personnelOrdersApi.client";

const items: PersonnelOrderItem[] = [
  {
    item_id: 10,
    order_id: 42,
    item_number: 1,
    item_type_code: "HIRE",
    item_status: "ACTIVE",
    employee_name: "Петрова Анна",
    payload: { basis_ids: ["application-1"] },
  },
];

const sampleOrder = {
  order_date: "2026-07-18",
  signed_by_name: "М. Тулеутаев",
  signed_by_position: "Директор",
};

function sampleState(overrides?: Partial<PersonnelOrderEditorialState>): PersonnelOrderEditorialState {
  return {
    order_id: 42,
    order_status: "DRAFT",
    editable: true,
    order_blocks: [
      {
        block_id: 1,
        scope: "order",
        locale: "kk",
        block_type: "title",
        generated_text: "Жұмысқа қабылдау туралы",
        override_text: null,
        effective_text: "Жұмысқа қабылдау туралы",
        review_status: "CURRENT",
        editable: true,
        revision: 1,
      },
      {
        block_id: 2,
        scope: "order",
        locale: "kk",
        block_type: "preamble",
        generated_text: "ҚР Еңбек кодексіне сәйкес",
        override_text: null,
        effective_text: "ҚР Еңбек кодексіне сәйкес",
        review_status: "CURRENT",
        editable: true,
        revision: 1,
      },
      {
        block_id: 3,
        scope: "order",
        locale: "kk",
        block_type: "closing",
        generated_text: "",
        override_text: null,
        effective_text: "",
        review_status: "CURRENT",
        editable: true,
        revision: 1,
      },
      {
        block_id: 101,
        scope: "order",
        locale: "ru",
        block_type: "title",
        generated_text: "О приёме на работу",
        override_text: null,
        effective_text: "О приёме на работу",
        review_status: "CURRENT",
        editable: true,
        revision: 1,
      },
      {
        block_id: 102,
        scope: "order",
        locale: "ru",
        block_type: "preamble",
        generated_text: "В соответствии с ТК РК",
        override_text: null,
        effective_text: "В соответствии с ТК РК",
        review_status: "CURRENT",
        editable: true,
        revision: 1,
      },
      {
        block_id: 103,
        scope: "order",
        locale: "ru",
        block_type: "closing",
        generated_text: "",
        override_text: null,
        effective_text: "",
        review_status: "CURRENT",
        editable: true,
        revision: 1,
      },
    ],
    items: [
      {
        order_item_id: 10,
        item_number: 1,
        item_type_code: "HIRE",
        basis_required: true,
        blocks: [
          {
            block_id: 11,
            scope: "item",
            order_item_id: 10,
            locale: "kk",
            block_type: "body",
            generated_text: "Петрова Аннаны қабылдау",
            override_text: null,
            effective_text: "Петрова Аннаны қабылдау",
            review_status: "CURRENT",
            editable: true,
            revision: 1,
          },
          {
            block_id: 12,
            scope: "item",
            order_item_id: 10,
            locale: "kk",
            block_type: "basis",
            generated_text: "Негіз: жеке өтініш.",
            override_text: null,
            effective_text: "Негіз: жеке өтініш.",
            review_status: "CURRENT",
            editable: true,
            revision: 1,
          },
          {
            block_id: 111,
            scope: "item",
            order_item_id: 10,
            locale: "ru",
            block_type: "body",
            generated_text: "Принять Петрову Анну",
            override_text: null,
            effective_text: "Принять Петрову Анну",
            review_status: "CURRENT",
            editable: true,
            revision: 1,
          },
          {
            block_id: 112,
            scope: "item",
            order_item_id: 10,
            locale: "ru",
            block_type: "basis",
            generated_text: "Основание: личное заявление.",
            override_text: null,
            effective_text: "Основание: личное заявление.",
            review_status: "CURRENT",
            editable: true,
            revision: 1,
          },
        ],
      },
    ],
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("PersonnelOrderEditorialTextEditor", () => {
  it('hides the position shortcut only for personal-data orders',async()=>{
    const personalItems=items.map(item=>({...item,item_type_code:'PERSONAL_DATA_CHANGE'}));
    const state=sampleState();state.items[0].item_type_code='PERSONAL_DATA_CHANGE';
    render(<PersonnelOrderEditorialTextEditor orderId={42} order={sampleOrder} items={personalItems} editable editorialState={state} onEditSourcePosition={vi.fn()}/>);
    await screen.findByText('Текст пункта');
    expect(screen.queryByRole('button',{name:'Изменить исходные данные должности'})).not.toBeInTheDocument();
  });
  it("keeps requisites and source position editing while hiding the education closing", async () => {
    const educationItems=items.map(item=>({...item,item_type_code:'EDUCATION_INFORMATION_CHANGE'}));
    const state=sampleState();state.items[0].item_type_code='EDUCATION_INFORMATION_CHANGE';
    const openSource=vi.fn();
    render(<PersonnelOrderEditorialTextEditor orderId={42} order={sampleOrder} items={educationItems} editable editorialState={state} onEditSourcePosition={openSource}/>);
    await screen.findByText('Текст пункта');
    expect(screen.queryByText('Заключительная часть')).not.toBeInTheDocument();
    expect(screen.getByTestId('personnel-order-editorial-requisites')).toBeInTheDocument();
    expect(screen.getByTestId('personnel-order-editorial-block-Негіз (мәтін құжатта)')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Изменить исходные данные должности'}));
    expect(openSource).toHaveBeenCalledExactlyOnceWith(10);
    expect(screen.queryByTestId('personnel-order-position-text-override')).not.toBeInTheDocument();
  });

  it.each(PERSONNEL_ORDER_CREATE_TYPE_OPTIONS.map(option=>option.value))("hides closing display for %s without altering stored blocks", async type => {
    const educationItems=items.map(item=>({...item,item_type_code:type}));
    const state=sampleState();
    const closing=state.order_blocks.find(block=>block.block_type==='closing'&&block.locale==='ru')!;
    closing.override_text='Сохранённая непустая заключительная часть';
    const before=JSON.stringify(state);
    render(<PersonnelOrderEditorialTextEditor orderId={42} order={sampleOrder} items={educationItems} editable editorialState={state}/>);
    await screen.findByTestId('personnel-order-editorial-requisites');
    for(const locale of ['kk','ru']){
      fireEvent.click(screen.getByTestId('personnel-order-editorial-locale-'+locale));
      expect(screen.queryByText('Заключительная часть')).not.toBeInTheDocument();
      expect(screen.queryByTestId('personnel-order-editorial-closing-toggle')).not.toBeInTheDocument();
    }
    expect(JSON.stringify(state)).toBe(before);
    expect(patchPersonnelOrderEditorialBlock).not.toHaveBeenCalled();
  });

  it("saves and restores the existing education basis override exactly in both languages", async () => {
    const educationItems=items.map(item=>({...item,item_type_code:'EDUCATION_INFORMATION_CHANGE'}));
    const state=sampleState();
    vi.mocked(getPersonnelOrderEditorial).mockImplementation(async()=>structuredClone(state));
    vi.mocked(patchPersonnelOrderEditorialBlock).mockImplementation(async(_id,blockId,body)=>{
      const block=state.items[0].blocks.find(block=>block.block_id===blockId)!;
      block.override_text=body.override_text;block.effective_text=body.override_text ?? '';block.revision+=1;
      return structuredClone(state);
    });
    let view=render(<PersonnelOrderEditorialTextEditor orderId={42} order={sampleOrder} items={educationItems} editable/>);
    const basis={kk:'Негіз: Сақталған KK негізі.\nЕкінші жол.',ru:'Основание: Сохранённое RU основание.\nВторая строка.'};
    for(const locale of ['kk','ru'] as const){
      fireEvent.click(await screen.findByTestId('personnel-order-editorial-locale-'+locale));
      const block=screen.getByTestId('personnel-order-editorial-block-'+(locale==='kk'?'Негіз (мәтін құжатта)':'Основание (текст в документе)'));
      fireEvent.click(within(block).getByTestId('personnel-order-editorial-edit'));
      fireEvent.change(within(block).getByTestId('personnel-order-editorial-textarea'),{target:{value:basis[locale]}});
      fireEvent.click(within(block).getByTestId('personnel-order-editorial-save'));
      await waitFor(()=>expect(within(block).getByTestId('personnel-order-editorial-readonly').textContent).toBe(basis[locale]));
    }
    view.unmount();
    view=render(<PersonnelOrderEditorialTextEditor orderId={42} order={sampleOrder} items={educationItems} editable/>);
    for(const locale of ['kk','ru'] as const){
      fireEvent.click(await screen.findByTestId('personnel-order-editorial-locale-'+locale));
      await waitFor(()=>expect(screen.getByTestId('personnel-order-editorial-block-'+(locale==='kk'?'Негіз (мәтін құжатта)':'Основание (текст в документе)')).textContent).toContain(basis[locale]));
    }
    expect(patchPersonnelOrderEditorialBlock).toHaveBeenCalledTimes(2);
    expect(updatePersonnelOrderItem).not.toHaveBeenCalled();
  });

  it("loads editorial state and shows document structure without technical fields", async () => {
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValue(sampleState());

    render(<PersonnelOrderEditorialTextEditor orderId={42} order={sampleOrder} items={items} editable />);

    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-editorial-editor")).toBeInTheDocument();
    });

    expect(screen.getByText("Текст приказа")).toBeInTheDocument();
    expect(
      screen.getByText("Редактирование казахской версии приказа"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("personnel-order-editorial-locale-tabs")).toBeInTheDocument();
    expect(screen.getByTestId("personnel-order-editorial-locale-kk")).toBeInTheDocument();
    expect(screen.getByTestId("personnel-order-editorial-locale-ru")).toBeInTheDocument();
    expect(
      screen.queryByText(/Русский язык будет доступен на следующем этапе/i),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Заголовок")).toBeInTheDocument();
    expect(screen.getByText("Преамбула")).toBeInTheDocument();
    expect(screen.getByText("Пункт №1")).toBeInTheDocument();
    expect(screen.getByText("Петрова Анна")).toBeInTheDocument();
    expect(screen.getByText("Негіз (мәтін құжатта)")).toBeInTheDocument();
    expect(screen.getByText("Негіз: жеке өтініш.")).toBeInTheDocument();
    expect(screen.queryByTestId("personnel-order-editorial-basis-block")).not.toBeInTheDocument();
    expect(screen.queryByText("Заключительная часть")).not.toBeInTheDocument();

    expect(screen.queryByText(/fingerprint/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/generator_key/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/block_type/i)).not.toBeInTheDocument();
    expect(screen.getAllByText("Generated").length).toBeGreaterThan(0);
  });

  it("auto-generates full editorial state when required locales are missing in DRAFT", async () => {
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValue({
      order_id: 42,
      order_status: "DRAFT",
      editable: true,
      order_blocks: [],
      items: [],
    });
    vi.mocked(generatePersonnelOrderEditorial).mockResolvedValue(sampleState());

    render(<PersonnelOrderEditorialTextEditor orderId={42} order={sampleOrder} items={items} editable />);

    await waitFor(() => {
      expect(generatePersonnelOrderEditorial).toHaveBeenCalledWith(42);
    });
    await waitFor(() => {
      expect(screen.getByText("Жұмысқа қабылдау туралы")).toBeInTheDocument();
    });
  });

  it("does not auto-generate again when both locales already exist", async () => {
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValue(sampleState());

    render(<PersonnelOrderEditorialTextEditor orderId={42} order={sampleOrder} items={items} editable />);

    await waitFor(() => {
      expect(screen.getByText("Жұмысқа қабылдау туралы")).toBeInTheDocument();
    });
    expect(generatePersonnelOrderEditorial).not.toHaveBeenCalled();
  });

  it.each(['EMPLOYER_INITIATIVE','CONTRACT_EXPIRATION'] as const)('changes the visible termination reason to %s, reopens it, and keeps the manual basis',async reason=>{
    let saved:PersonnelOrderItem={...items[0],item_type_code:'TERMINATION',payload:{termination_reason:'EMPLOYEE_INITIATIVE',basis_other_text:'Приказ кадровика № 7',legacy_flag:true}};
    const manualBasis={ru:'Основание: приказ кадровика № 7.',kk:'Негіз: кадр бөлімінің № 7 бұйрығы.'};
    let editorial=sampleState();editorial.items[0].item_type_code='TERMINATION';
    for(const block of editorial.items[0].blocks)if(block.block_type==='basis'){
      block.override_text=manualBasis[block.locale as 'ru'|'kk'];block.effective_text=block.override_text;
    }
    vi.mocked(getPersonnelOrder).mockImplementation(async()=>({order:{order_id:42},items:[structuredClone(saved)]} as PersonnelOrderDetailResponse));
    vi.mocked(getPersonnelOrderEditorial).mockImplementation(async()=>structuredClone(editorial));
    vi.mocked(updatePersonnelOrderItem).mockImplementation(async(_order,_item,body)=>{
      saved={...saved,payload:body.payload!};
      return {order:{order_id:42},items:[structuredClone(saved)]} as PersonnelOrderDetailResponse;
    });
    vi.mocked(generatePersonnelOrderEditorial).mockImplementation(async()=>{
      editorial=structuredClone(editorial);
      for(const block of editorial.items[0].blocks)if(block.block_type==='body'){
        block.generated_text=block.effective_text=block.locale==='ru'
          ? reason==='CONTRACT_EXPIRATION'?'В связи с истечением срока трудового договора':'по инициативе работодателя'
          : reason==='CONTRACT_EXPIRATION'?'Еңбек шарты мерзімінің аяқталуына байланысты':'жұмыс берушінің бастамасы бойынша';
      }
      return structuredClone(editorial);
    });
    const beforeGenerate=vi.fn().mockResolvedValue(true);
    function Harness(){const [current,setCurrent]=React.useState(saved);return <PersonnelOrderEditorialTextEditor orderId={42} order={sampleOrder} items={[current]} editable beforeGenerate={beforeGenerate} onOrderChanged={detail=>setCurrent(detail.items[0])}/>;}
    let view=render(<Harness/>);
    const selector=await screen.findByTestId('personnel-order-termination-reason-10');
    expect(within(selector).getByRole('combobox',{name:'Причина расторжения трудового договора'})).toHaveValue('EMPLOYEE_INITIATIVE');
    expect([...within(selector).getByRole('combobox').querySelectorAll('option')].map(option=>option.value)).toEqual(['','EMPLOYEE_INITIATIVE','EMPLOYER_INITIATIVE','CONTRACT_EXPIRATION']);
    expect(selector.compareDocumentPosition(screen.getByTestId('personnel-order-editorial-block-Негіз (мәтін құжатта)')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    fireEvent.change(within(selector).getByRole('combobox'),{target:{value:reason}});
    fireEvent.click(within(selector).getByRole('button',{name:'Сохранить причину'}));
    await waitFor(()=>expect(generatePersonnelOrderEditorial).toHaveBeenCalledWith(42));
    expect(beforeGenerate).toHaveBeenCalledOnce();
    expect(updatePersonnelOrderItem).toHaveBeenCalledWith(42,10,{payload:{termination_reason:reason,basis_other_text:'Приказ кадровика № 7',legacy_flag:true}});
    expect(saved.payload).not.toHaveProperty('legal_basis_article');
    expect(screen.getByTestId('personnel-order-editorial-block-Текст пункта').textContent).toContain(reason==='CONTRACT_EXPIRATION'?'Еңбек шарты мерзімінің аяқталуына байланысты':'жұмыс берушінің бастамасы бойынша');
    expect(screen.getByTestId('personnel-order-editorial-block-Негіз (мәтін құжатта)').textContent).toContain(manualBasis.kk);
    view.unmount();view=render(<Harness/>);
    expect((await screen.findByTestId('personnel-order-termination-reason-10')).querySelector('select')).toHaveValue(reason);
    fireEvent.click(screen.getByTestId('personnel-order-editorial-locale-ru'));
    expect(screen.getByTestId('personnel-order-editorial-block-Текст пункта').textContent).toContain(reason==='CONTRACT_EXPIRATION'?'В связи с истечением срока трудового договора':'по инициативе работодателя');
    expect(screen.getByTestId('personnel-order-editorial-block-Основание (текст в документе)').textContent).toContain(manualBasis.ru);
    view.unmount();
  });

  it('shows a legacy free-text termination reason without enabling edits on a locked order',async()=>{
    const legacy='по соглашению сторон';
    const item={...items[0],item_type_code:'TERMINATION',payload:{termination_reason:legacy}};
    const state=sampleState();state.items[0].item_type_code='TERMINATION';state.editable=false;state.order_status='SIGNED';
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValue(state);
    render(<PersonnelOrderEditorialTextEditor orderId={42} order={sampleOrder} items={[item]} editable={false}/>);
    const selector=await screen.findByTestId('personnel-order-termination-reason-10');
    expect(within(selector).getByRole('combobox')).toHaveValue(legacy);
    expect(within(selector).getByRole('combobox')).toBeDisabled();
    expect(within(selector).getByRole('option',{name:legacy})).toBeInTheDocument();
    expect(within(selector).queryByRole('button',{name:'Сохранить причину'})).not.toBeInTheDocument();
    expect(updatePersonnelOrderItem).not.toHaveBeenCalled();
  });

  it.each([
    ['EMPLOYER_INITIATIVE','По инициативе работодателя','Жұмыс берушінің бастамасы бойынша'],
    ['CONTRACT_EXPIRATION','В связи с истечением срока трудового договора','Еңбек шарты мерзімінің аяқталуына байланысты'],
  ] as const)("saves and reopens manual RU/KK termination body additions for %s", async (reason,ru,kk) => {
    const terminationItems=items.map(item=>({...item,item_type_code:'TERMINATION',payload:{termination_reason:reason}}));
    const state=sampleState();state.items[0].item_type_code='TERMINATION';
    vi.mocked(getPersonnelOrderEditorial).mockImplementation(async()=>structuredClone(state));
    vi.mocked(patchPersonnelOrderEditorialBlock).mockImplementation(async(_id,blockId,body)=>{
      const block=state.items[0].blocks.find(block=>block.block_id===blockId)!;
      block.override_text=body.override_text;block.effective_text=body.override_text ?? '';block.revision+=1;
      return structuredClone(state);
    });
    let view=render(<PersonnelOrderEditorialTextEditor orderId={42} order={sampleOrder} items={terminationItems} editable/>);
    const manual={ru:`${ru}. Конкретная причина и правовая ссылка RU — вручную.`,kk:`${kk}. Нақты себеп пен құқықтық сілтеме KK — қолмен.`};
    for(const locale of ['kk','ru'] as const){
      fireEvent.click(await screen.findByTestId('personnel-order-editorial-locale-'+locale));
      const block=screen.getByTestId('personnel-order-editorial-block-Текст пункта');
      fireEvent.click(within(block).getByTestId('personnel-order-editorial-edit'));
      fireEvent.change(within(block).getByTestId('personnel-order-editorial-textarea'),{target:{value:manual[locale]}});
      fireEvent.click(within(block).getByTestId('personnel-order-editorial-save'));
      await waitFor(()=>expect(within(block).getByTestId('personnel-order-editorial-readonly').textContent).toBe(manual[locale]));
    }
    view.unmount();
    view=render(<PersonnelOrderEditorialTextEditor orderId={42} order={sampleOrder} items={terminationItems} editable/>);
    for(const locale of ['kk','ru'] as const){
      fireEvent.click(await screen.findByTestId('personnel-order-editorial-locale-'+locale));
      await waitFor(()=>expect(screen.getByTestId('personnel-order-editorial-block-Текст пункта').textContent).toContain(manual[locale]));
    }
    expect(terminationItems[0].payload.termination_reason).toBe(reason);
    expect(updatePersonnelOrderItem).not.toHaveBeenCalled();
  });


  it("asks for confirmation before manual generate and regenerates all locales", async () => {
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValue(sampleState());
    vi.mocked(generatePersonnelOrderEditorial).mockResolvedValue(sampleState());
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<PersonnelOrderEditorialTextEditor orderId={42} order={sampleOrder} items={items} editable />);

    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-editorial-generate")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("personnel-order-editorial-generate"));

    expect(confirmSpy).toHaveBeenCalled();
    const message = String(confirmSpy.mock.calls[0]?.[0] ?? "");
    expect(message).toContain("Пересформировать текст приказа?");
    expect(message).toContain("Будут обновлены автоматически сформированные тексты приказа.");
    expect(message).toContain("Продолжить?");
    expect(message).not.toContain("Ручные изменения");

    await waitFor(() => {
      expect(generatePersonnelOrderEditorial).toHaveBeenCalledWith(42);
    });
  });

  it("saves a pending structured item before generating the document", async () => {
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValue(sampleState());
    vi.mocked(generatePersonnelOrderEditorial).mockResolvedValue(sampleState());
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const beforeGenerate = vi.fn(async () => true);

    render(<PersonnelOrderEditorialTextEditor orderId={42} order={sampleOrder} items={items} editable beforeGenerate={beforeGenerate} />);
    fireEvent.click(await screen.findByTestId("personnel-order-editorial-generate"));

    await waitFor(() => expect(beforeGenerate).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(generatePersonnelOrderEditorial).toHaveBeenCalledWith(42));
    expect(beforeGenerate.mock.invocationCallOrder[0]).toBeLessThan(
      vi.mocked(generatePersonnelOrderEditorial).mock.invocationCallOrder[0],
    );
  });

  it("does not generate when the pending item cannot be saved", async () => {
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValue(sampleState());
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const beforeGenerate = vi.fn(async () => false);

    render(<PersonnelOrderEditorialTextEditor orderId={42} order={sampleOrder} items={items} editable beforeGenerate={beforeGenerate} />);
    fireEvent.click(await screen.findByTestId("personnel-order-editorial-generate"));

    await waitFor(() => expect(beforeGenerate).toHaveBeenCalledTimes(1));
    expect(generatePersonnelOrderEditorial).not.toHaveBeenCalled();
    expect(screen.getByText("Не удалось сохранить пункт. Формирование текста не выполнено.")).toBeInTheDocument();
  });

  it("shows only kk blocks on kk tab even when ru blocks are present in state", async () => {
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValue(sampleState());

    render(<PersonnelOrderEditorialTextEditor orderId={42} order={sampleOrder} items={items} editable />);

    await waitFor(() => {
      expect(screen.getByText("Жұмысқа қабылдау туралы")).toBeInTheDocument();
    });
    expect(screen.queryByText("О приёме на работу")).not.toBeInTheDocument();
  });

  it("shows ru blocks when Russian tab is selected", async () => {
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValue(sampleState());

    render(<PersonnelOrderEditorialTextEditor orderId={42} order={sampleOrder} items={items} editable />);

    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-editorial-locale-ru")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("personnel-order-editorial-locale-ru"));

    await waitFor(() => {
      expect(screen.getByText("О приёме на работу")).toBeInTheDocument();
    });
    expect(screen.queryByText("Жұмысқа қабылдау туралы")).not.toBeInTheDocument();
  });

  it("shows the editorial BASIS as document text without a second structural editor", async () => {
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValue(sampleState());
    render(<PersonnelOrderEditorialTextEditor orderId={42} order={sampleOrder} items={items} editable />);

    expect(await screen.findByText("Негіз (мәтін құжатта)")).toBeInTheDocument();
    expect(screen.getByText("Негіз: жеке өтініш.")).toBeInTheDocument();
    expect(screen.queryByTestId("personnel-order-editorial-basis-edit")).not.toBeInTheDocument();
    expect(screen.queryByTestId("personnel-order-editorial-basis-editor")).not.toBeInTheDocument();
  });

  it("saves Russian override with expected revision", async () => {
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValue(sampleState());
    const afterSave = sampleState();
    afterSave.order_blocks = afterSave.order_blocks.map((b) =>
      b.block_id === 101
        ? {
            ...b,
            override_text: "Новый заголовок",
            effective_text: "Новый заголовок",
            revision: 2,
            review_status: "CURRENT",
          }
        : b,
    );
    vi.mocked(patchPersonnelOrderEditorialBlock).mockResolvedValue(afterSave);

    render(<PersonnelOrderEditorialTextEditor orderId={42} order={sampleOrder} items={items} editable />);

    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-editorial-locale-ru")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("personnel-order-editorial-locale-ru"));

    await waitFor(() => {
      expect(screen.getByText("О приёме на работу")).toBeInTheDocument();
    });

    const titleSection = screen.getByTestId("personnel-order-editorial-block-Заголовок");
    fireEvent.click(titleSection.querySelector('[data-testid="personnel-order-editorial-edit"]')!);

    const textarea = screen.getByTestId("personnel-order-editorial-textarea");
    fireEvent.change(textarea, { target: { value: "Новый заголовок" } });
    fireEvent.click(screen.getByTestId("personnel-order-editorial-save"));

    await waitFor(() => {
      expect(patchPersonnelOrderEditorialBlock).toHaveBeenCalledWith(42, 101, {
        override_text: "Новый заголовок",
        expected_revision: 1,
      });
    });
    await waitFor(() => {
      expect(screen.getByText("Новый заголовок")).toBeInTheDocument();
      expect(screen.getByText("Edited")).toBeInTheDocument();
    });
  });

  it("auto-generates when only one locale is present", async () => {
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValue({
      order_id: 42,
      order_status: "DRAFT",
      editable: true,
      order_blocks: [
        {
          block_id: 1,
          scope: "order",
          locale: "kk",
          block_type: "title",
          generated_text: "Жұмысқа қабылдау туралы",
          override_text: null,
          effective_text: "Жұмысқа қабылдау туралы",
          review_status: "CURRENT",
          editable: true,
          revision: 1,
        },
      ],
      items: [],
    });
    vi.mocked(generatePersonnelOrderEditorial).mockResolvedValue(sampleState());

    render(<PersonnelOrderEditorialTextEditor orderId={42} order={sampleOrder} items={items} editable />);

    await waitFor(() => {
      expect(generatePersonnelOrderEditorial).toHaveBeenCalledWith(42);
    });
  });

  it("skips generate when user declines confirmation", async () => {
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValue(sampleState());
    vi.spyOn(window, "confirm").mockReturnValue(false);

    render(<PersonnelOrderEditorialTextEditor orderId={42} order={sampleOrder} items={items} editable />);

    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-editorial-generate")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("personnel-order-editorial-generate"));
    expect(generatePersonnelOrderEditorial).not.toHaveBeenCalled();
  });

  it("renders the generate action as the primary blue button", async () => {
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValue(sampleState());
    render(<PersonnelOrderEditorialTextEditor orderId={42} order={sampleOrder} items={items} editable />);

    const button = await screen.findByTestId("personnel-order-editorial-generate");
    expect(button).toHaveClass("bg-blue-700", "text-white");
  });

  it("saves override with expected revision and updates status to Edited", async () => {
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValue(sampleState());
    const afterSave = sampleState();
    afterSave.order_blocks = afterSave.order_blocks.map((b) =>
      b.block_type === "title"
        ? {
            ...b,
            override_text: "Жаңа тақырып",
            effective_text: "Жаңа тақырып",
            revision: 2,
            review_status: "CURRENT",
          }
        : b,
    );
    vi.mocked(patchPersonnelOrderEditorialBlock).mockResolvedValue(afterSave);

    render(<PersonnelOrderEditorialTextEditor orderId={42} order={sampleOrder} items={items} editable />);

    await waitFor(() => {
      expect(screen.getByText("Жұмысқа қабылдау туралы")).toBeInTheDocument();
    });

    const titleSection = screen.getByTestId("personnel-order-editorial-block-Заголовок");
    fireEvent.click(titleSection.querySelector('[data-testid="personnel-order-editorial-edit"]')!);

    const textarea = screen.getByTestId("personnel-order-editorial-textarea");
    fireEvent.change(textarea, { target: { value: "Жаңа тақырып" } });
    fireEvent.click(screen.getByTestId("personnel-order-editorial-save"));

    await waitFor(() => {
      expect(patchPersonnelOrderEditorialBlock).toHaveBeenCalledWith(42, 1, {
        override_text: "Жаңа тақырып",
        expected_revision: 1,
      });
    });
    await waitFor(() => {
      expect(screen.getByText("Жаңа тақырып")).toBeInTheDocument();
      expect(screen.getByText("Edited")).toBeInTheDocument();
    });
  });

  it("resets override to generated text", async () => {
    const withOverride = sampleState();
    withOverride.order_blocks = withOverride.order_blocks.map((b) =>
      b.block_type === "title"
        ? {
            ...b,
            override_text: "Қолмен",
            effective_text: "Қолмен",
            revision: 2,
          }
        : b,
    );
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValue(withOverride);
    vi.mocked(resetPersonnelOrderEditorialBlock).mockResolvedValue(sampleState());
    vi.spyOn(window, "confirm").mockReturnValue(true);

    render(<PersonnelOrderEditorialTextEditor orderId={42} order={sampleOrder} items={items} editable />);

    await waitFor(() => {
      expect(screen.getByText("Қолмен")).toBeInTheDocument();
    });

    const titleSection = screen.getByTestId("personnel-order-editorial-block-Заголовок");
    fireEvent.click(titleSection.querySelector('[data-testid="personnel-order-editorial-reset"]')!);

    await waitFor(() => {
      expect(resetPersonnelOrderEditorialBlock).toHaveBeenCalledWith(42, 1);
    });
    await waitFor(() => {
      expect(screen.getByText("Жұмысқа қабылдау туралы")).toBeInTheDocument();
    });
  });

  it("hides edit actions when not DRAFT-editable", async () => {
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValue(
      sampleState({ order_status: "READY_FOR_SIGNATURE", editable: false }),
    );

    render(
      <PersonnelOrderEditorialTextEditor
        orderId={42}
        order={sampleOrder}
        items={items}
        editable={false}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("Жұмысқа қабылдау туралы")).toBeInTheDocument();
    });

    expect(screen.queryByTestId("personnel-order-editorial-edit")).not.toBeInTheDocument();
    expect(screen.queryByTestId("personnel-order-editorial-generate")).not.toBeInTheDocument();
    expect(screen.getByText(/только для просмотра/i)).toBeInTheDocument();
  });

  it("shows structured requisites preview independently of the hidden closing section", async () => {
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValue(sampleState());

    render(<PersonnelOrderEditorialTextEditor orderId={42} order={sampleOrder} items={items} editable />);

    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-editorial-requisites")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("personnel-order-editorial-locale-ru"));

    expect(screen.getByTestId("personnel-order-requisites-date")).toHaveTextContent("18 июля 2026 года");
    expect(screen.getByTestId("personnel-order-requisites-signatory")).toHaveTextContent("Директор");
    expect(screen.getByTestId("personnel-order-requisites-signatory")).toHaveTextContent("М. Тулеутаев");
  });

  it("updates structured requisites preview when saved order header changes", async () => {
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValue(sampleState());

    const { rerender } = render(
      <PersonnelOrderEditorialTextEditor
        orderId={42}
        order={{ order_date: null, signed_by_name: null, signed_by_position: null }}
        items={items}
        editable
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-requisites-preview-empty")).toBeInTheDocument();
    });

    rerender(
      <PersonnelOrderEditorialTextEditor orderId={42} order={sampleOrder} items={items} editable />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-requisites-signatory")).toHaveTextContent("Директор");
    });
    fireEvent.click(screen.getByTestId("personnel-order-editorial-locale-ru"));
    expect(screen.getByTestId("personnel-order-requisites-signatory")).toHaveTextContent("М. Тулеутаев");
    expect(screen.getByTestId("personnel-order-requisites-date")).toHaveTextContent("18 июля 2026 года");
  });

  it("keeps bilingual requisites visible without closing editing controls or writes", async () => {
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValue(sampleState());
    vi.mocked(patchPersonnelOrderEditorialBlock).mockResolvedValue(sampleState());

    render(<PersonnelOrderEditorialTextEditor orderId={42} order={sampleOrder} items={items} editable />);

    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-editorial-requisites")).toBeInTheDocument();
    });

    expect(screen.queryByTestId("personnel-order-editorial-block-Заключительная часть")).not.toBeInTheDocument();
    expect(screen.queryByTestId("personnel-order-editorial-closing-toggle")).not.toBeInTheDocument();
    expect(patchPersonnelOrderEditorialBlock).not.toHaveBeenCalled();

    fireEvent.click(screen.getByTestId("personnel-order-editorial-locale-ru"));

    expect(screen.getByTestId("personnel-order-requisites-date")).toHaveTextContent("18 июля 2026 года");
    expect(screen.getByTestId("personnel-order-requisites-signatory")).toHaveTextContent("М. Тулеутаев");
  });

  it("resets only the Russian item body to its generated Russian text", async () => {
    const withRussianOverride = sampleState();
    withRussianOverride.items[0]!.blocks = withRussianOverride.items[0]!.blocks.map((block) =>
      block.block_id === 111
        ? { ...block, override_text: "РУЧНОЙ RU", effective_text: "РУЧНОЙ RU", revision: 2 }
        : block,
    );
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValue(withRussianOverride);
    vi.mocked(resetPersonnelOrderEditorialBlock).mockResolvedValue(sampleState());
    vi.spyOn(window, "confirm").mockReturnValue(true);

    render(<PersonnelOrderEditorialTextEditor orderId={42} order={sampleOrder} items={items} editable />);
    await screen.findByTestId("personnel-order-editorial-locale-ru");
    fireEvent.click(screen.getByTestId("personnel-order-editorial-locale-ru"));
    const item = await screen.findByTestId("personnel-order-editorial-item-10");
    expect(item).toHaveTextContent("РУЧНОЙ RU");
    expect(item).toHaveTextContent("Ручной текст пункта имеет приоритет; чтобы применить название должности, верните автоматически сформированный текст.");
    fireEvent.click(item.querySelector('[data-testid="personnel-order-editorial-reset"]')!);

    await waitFor(() => {
      expect(resetPersonnelOrderEditorialBlock).toHaveBeenCalledWith(42, 111);
      expect(item).toHaveTextContent("Принять Петрову Анну");
    });
    expect(sampleState().items[0]!.blocks.find((block) => block.block_id === 11)?.effective_text).toBe("Петрова Аннаны қабылдау");
  });

  it("persists separate position text overrides without changing the item employee or position", async () => {
    const itemWithAssignment: PersonnelOrderItem = {
      ...items[0]!,
      employee_id: 77,
      payload: { ...items[0]!.payload, position_id: 20, assignment: { position: { ru: "Медсестра", kk: "мейіргер" } } },
    };
    const returnedDetail = {} as PersonnelOrderDetailResponse;
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValue(sampleState());
    vi.mocked(updatePersonnelOrderItem).mockResolvedValue(returnedDetail);
    const changed = vi.fn();

    const { rerender } = render(
      <PersonnelOrderEditorialTextEditor orderId={42} order={sampleOrder} items={[itemWithAssignment]} editable onOrderChanged={changed} />,
    );
    const editor = await screen.findByTestId("personnel-order-position-text-override");
    const fields = editor.querySelectorAll("input");
    fireEvent.change(fields[0]!, { target: { value: "медицинский брат" } });
    fireEvent.change(fields[1]!, { target: { value: "мейіргер" } });
    fireEvent.click(editor.querySelector("button")!);

    await waitFor(() => {
      expect(updatePersonnelOrderItem).toHaveBeenCalledWith(42, 10, expect.objectContaining({
        employee_id: 77,
        payload: expect.objectContaining({
          position_id: 20,
          position_text_override: { ru: "медицинский брат", kk: "мейіргер" },
        }),
      }));
      expect(changed).toHaveBeenCalledWith(returnedDetail);
    });

    const rereadItem: PersonnelOrderItem = {
      ...itemWithAssignment,
      payload: {
        ...itemWithAssignment.payload,
        position_text_override: { ru: "медицинский брат", kk: "мейіргер" },
      },
    };
    rerender(<PersonnelOrderEditorialTextEditor orderId={42} order={sampleOrder} items={[rereadItem]} editable />);
    const reread = await screen.findByTestId("personnel-order-position-text-override");
    expect(reread.querySelectorAll("input")[0]).toHaveValue("медицинский брат");
    expect(reread.querySelectorAll("input")[1]).toHaveValue("мейіргер");
  });
});
